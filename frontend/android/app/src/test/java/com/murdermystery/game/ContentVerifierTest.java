package com.murdermystery.game;

import static org.junit.Assert.*;
import java.io.File;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Before;
import org.junit.Test;
import org.junit.Rule;
import org.junit.rules.TemporaryFolder;

public class ContentVerifierTest {
    @Rule public TemporaryFolder files = new TemporaryFolder();
    private KeyPair pair;
    private ContentVerifier verifier;
    private final String id = "ad60c7e0-1f56-4fc3-bcaa-705910d03304";
    @Before public void setup() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC");
        generator.initialize(new ECGenParameterSpec("secp256r1"));
        pair = generator.generateKeyPair();
        JSONObject config = new JSONObject().put("publisher", "tests")
            .put("keys", new JSONObject().put("test", Base64.getEncoder().encodeToString(pair.getPublic().getEncoded())))
            .put("allowed_hosts", new JSONArray().put("github.com"));
        verifier = new ContentVerifier(config, value -> Base64.getDecoder().decode(value));
    }
    private byte[] sign(JSONObject payload, String domain) throws Exception {
        byte[] raw = payload.toString().getBytes(StandardCharsets.UTF_8);
        Signature signing = Signature.getInstance("SHA256withECDSA");
        signing.initSign(pair.getPrivate()); signing.update((domain + "\n").getBytes(StandardCharsets.US_ASCII)); signing.update(raw);
        return new JSONObject().put("envelope_version", 1).put("algorithm", "SHA256withECDSA").put("key_id", "test")
            .put("payload_b64", Base64.getEncoder().encodeToString(raw))
            .put("signature_b64", Base64.getEncoder().encodeToString(signing.sign())).toString().getBytes(StandardCharsets.UTF_8);
    }
    private JSONObject entry() throws Exception {
        return new JSONObject().put("story_id", id).put("content_version", 1).put("min_engine_version", 1)
            .put("bundle_format", 1).put("package_format", 1).put("num_characters", 4).put("estimated_minutes", 30)
            .put("bytes", 1000).put("title", "原创案卷").put("summary", "公开简介").put("author", "作者")
            .put("license", "AGPL-3.0-only").put("difficulty", "入门").put("status", "active")
            .put("sha256", "1".repeat(64)).put("download_urls", new JSONArray().put("https://github.com/tests/data.mmstory"));
    }
    private JSONObject catalog(JSONObject... entries) throws Exception {
        JSONArray list = new JSONArray(); for (JSONObject entry : entries) list.put(entry);
        return new JSONObject().put("kind", "murder-mystery-catalog").put("catalog_format", 1).put("catalog_revision", 1)
            .put("publisher", "tests").put("channel", "stable").put("issued_at", "2026-10-05T12:00:00+08:00").put("entries", list);
    }
    private File zip(Map<String, byte[]> data, JSONObject manifest) throws Exception {
        File file = files.newFile();
        try (ZipOutputStream output = new ZipOutputStream(Files.newOutputStream(file.toPath()))) {
            for (Map.Entry<String, byte[]> entry : data.entrySet()) {
                output.putNextEntry(new ZipEntry(entry.getKey())); output.write(entry.getValue()); output.closeEntry();
            }
            output.putNextEntry(new ZipEntry("bundle.json")); output.write(sign(manifest, "MMG-BUNDLE-V1")); output.closeEntry();
        }
        return file;
    }
    private Map<String, byte[]> data() {
        Map<String, byte[]> data = new LinkedHashMap<>();
        data.put("package.json", "{\"正文\":\"测试\"}".getBytes(StandardCharsets.UTF_8));
        data.put("LICENSE", "license".getBytes(StandardCharsets.UTF_8));
        data.put("SOURCE.txt", "source".getBytes(StandardCharsets.UTF_8));
        return data;
    }
    private JSONObject manifest(Map<String, byte[]> data) throws Exception {
        JSONArray rows = new JSONArray();
        for (Map.Entry<String, byte[]> entry : data.entrySet()) rows.put(new JSONObject().put("path", entry.getKey())
            .put("bytes", entry.getValue().length).put("sha256", ContentVerifier.hex(entry.getValue())));
        return new JSONObject().put("kind", "murder-mystery-story-bundle").put("publisher", "tests").put("bundle_format", 1)
            .put("package_format", 1).put("story_id", id).put("content_version", 1).put("min_engine_version", 1)
            .put("source_commit", "1".repeat(40)).put("files", rows);
    }
    private interface Operation { void run() throws Exception; }
    private void fails(String code, Operation operation) throws Exception {
        try { operation.run(); fail("invalid content accepted"); }
        catch (ContentVerifier.Failure error) { assertEquals(code, error.code); }
    }
    @Test public void realSignatureAllowsCatalogAndUnknownEngineIsPerEntry() throws Exception {
        JSONObject supported = entry(), future = entry().put("story_id", "ad60c7e0-1f56-4fc3-bcaa-705910d03305").put("min_engine_version", 2).put("num_characters", 9);
        JSONObject result = verifier.catalog(sign(catalog(supported, future), "MMG-CATALOG-V1"));
        assertEquals(2, result.getJSONArray("entries").length());
        assertTrue(ContentVerifier.compatible(result.getJSONArray("entries").getJSONObject(0)));
        assertFalse(ContentVerifier.compatible(result.getJSONArray("entries").getJSONObject(1)));
    }
    @Test public void tamperingUnknownKeysAndWrongSignatureDomainAreRejected() throws Exception {
        byte[] good = sign(catalog(entry()), "MMG-CATALOG-V1");
        JSONObject wrapper = new JSONObject(new String(good, StandardCharsets.UTF_8));
        wrapper.put("payload_b64", Base64.getEncoder().encodeToString(catalog(entry().put("title", "被改写")).toString().getBytes(StandardCharsets.UTF_8)));
        final byte[] altered = wrapper.toString().getBytes(StandardCharsets.UTF_8);
        fails("SIGNATURE_INVALID", () -> verifier.catalog(altered));
        wrapper = new JSONObject(new String(good, StandardCharsets.UTF_8)).put("key_id", "unknown");
        final byte[] unknown = wrapper.toString().getBytes(StandardCharsets.UTF_8);
        fails("SIGNATURE_INVALID", () -> verifier.catalog(unknown));
        fails("SIGNATURE_INVALID", () -> verifier.catalog(sign(catalog(entry()), "MMG-BUNDLE-V1")));
    }
    @Test public void validBundleExtractsOnlyVerifiedBytes() throws Exception {
        Map<String, byte[]> data = data();
        File output = files.newFolder();
        verifier.extract(zip(data, manifest(data)), output);
        assertArrayEquals(data.get("package.json"), Files.readAllBytes(new File(output, "package.json").toPath()));
        assertFalse(new File(output, "complete.json").exists());
    }
    @Test public void alteredFilesUnlistedFilesAndTraversalCannotInstall() throws Exception {
        Map<String, byte[]> data = data();
        JSONObject signedManifest = manifest(data);
        data.put("package.json", "broken".getBytes(StandardCharsets.UTF_8));
        fails("HASH_MISMATCH", () -> verifier.extract(zip(data, signedManifest), files.newFolder()));
        Map<String, byte[]> extra = data();
        JSONObject original = manifest(extra);
        extra.put("extra.txt", new byte[]{1});
        fails("PACKAGE_INVALID", () -> verifier.extract(zip(extra, original), files.newFolder()));
        Map<String, byte[]> traversal = data();
        traversal.put("../escape.txt", new byte[]{1});
        fails("PACKAGE_INVALID", () -> verifier.extract(zip(traversal, manifest(traversal)), files.newFolder()));
    }
    @Test public void symlinkModeAndEncryptedFlagsAreRejectedBeforeExtraction() throws Exception {
        File link = zip(data(), manifest(data()));
        patchCentral(link, 38, new byte[]{0, 0, (byte)0xff, (byte)0xa1});
        fails("PACKAGE_INVALID", () -> verifier.extract(link, files.newFolder()));
        File encrypted = zip(data(), manifest(data()));
        patchCentral(encrypted, 8, new byte[]{1, 0});
        fails("PACKAGE_INVALID", () -> verifier.extract(encrypted, files.newFolder()));
    }
    private void patchCentral(File zip, int relative, byte[] patch) throws Exception {
        byte[] raw = Files.readAllBytes(zip.toPath());
        for (int offset = 0; offset < raw.length - 4; offset++) {
            if (raw[offset] == 0x50 && raw[offset + 1] == 0x4b && raw[offset + 2] == 1 && raw[offset + 3] == 2) {
                try (RandomAccessFile file = new RandomAccessFile(zip, "rw")) { file.seek(offset + relative); file.write(patch); }
                return;
            }
        }
        fail("central directory missing");
    }
    @Test public void duplicateJsonKeysMalformedNumbersAndUnsafeUrlsAreRejected() throws Exception {
        for (String json : new String[]{"{\"version\":1,\"version\":2}", "{\"v\":01}", "{\"v\":NaN}", "{\"v\":1e999}", "{\"a\":1,\"\\u0061\":2}"}) {
            try { ContentJson.parse(json); fail("bad JSON accepted"); } catch (IllegalArgumentException expected) {}
        }
        for (String url : new String[]{"http://github.com/x", "https://github.com.evil.example/x", "https://user@github.com/x", "https://127.0.0.1/x"}) {
            fails("PACKAGE_INVALID", () -> verifier.allowedUrl(url));
        }
        fails("PACKAGE_INVALID", () -> verifier.catalog(sign(catalog(entry(), entry()), "MMG-CATALOG-V1")));
        fails("PACKAGE_INVALID", () -> verifier.catalog(sign(catalog(entry().put("content_version", 1.5)), "MMG-CATALOG-V1")));
    }
    @Test public void oversizedManifestOrFutureEngineRejectsInstallation() throws Exception {
        fails("PACKAGE_INVALID", () -> verifier.envelope(new byte[ContentVerifier.ENVELOPE_LIMIT + 1], "MMG-BUNDLE-V1"));
        Map<String, byte[]> data = data();
        JSONObject future = manifest(data).put("min_engine_version", 2);
        fails("ENGINE_UNSUPPORTED", () -> verifier.extract(zip(data, future), files.newFolder()));
    }
}
