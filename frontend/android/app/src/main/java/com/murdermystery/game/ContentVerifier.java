package com.murdermystery.game;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import android.util.Base64;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import org.json.JSONArray;
import org.json.JSONObject;

/** No network, credentials or activation: verify immutable data only. */
final class ContentVerifier {
    static final int ENGINE_VERSION = 1;
    static final int ENVELOPE_LIMIT = 2 * 1024 * 1024;
    static final int ZIP_LIMIT = 20 * 1024 * 1024;
    private final JSONObject config;
    interface Decoder { byte[] decode(String value); }
    private final Decoder decoder;
    ContentVerifier(JSONObject config) { this(config, value -> Base64.decode(value, Base64.DEFAULT)); }
    ContentVerifier(JSONObject config, Decoder decoder) { this.config = config; this.decoder = decoder; }
    static final class Failure extends Exception {
        final String code;
        Failure(String code, String message) { super(message); this.code = code; }
    }
    static int integer(JSONObject data, String key, int min, int max) throws Exception {
        Object value = data.get(key);
        if (!(value instanceof Integer || value instanceof Long)) throw new Failure("PACKAGE_INVALID", "内容版本或大小无效");
        long number = ((Number) value).longValue();
        if (number < min || number > max) throw new Failure("PACKAGE_INVALID", "内容版本或大小超过限制");
        return (int) number;
    }
    static String string(JSONObject data, String key, int max) throws Exception {
        Object value = data.get(key);
        if (!(value instanceof String) || ((String) value).isEmpty() || ((String) value).length() > max) throw new Failure("PACKAGE_INVALID", "内容字段缺失或过长");
        return (String) value;
    }
    static String id(JSONObject data, String key) throws Exception {
        String value = string(data, key, 36);
        if (!UUID.fromString(value).toString().equals(value)) throw new Failure("PACKAGE_INVALID", "剧本 ID 无效");
        return value;
    }
    static String hash(JSONObject data, String key) throws Exception {
        String value = string(data, key, 64);
        if (!value.matches("[a-f0-9]{64}") || value.matches("0{64}")) throw new Failure("PACKAGE_INVALID", "内容校验值无效");
        return value;
    }
    static String hex(byte[] data) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder output = new StringBuilder();
        for (byte value : digest) output.append(String.format("%02x", value & 255));
        return output.toString();
    }
    static String fileHash(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream stream = new java.io.FileInputStream(file)) {
            byte[] buffer = new byte[8192]; int count;
            while ((count = stream.read(buffer)) != -1) digest.update(buffer, 0, count);
        }
        StringBuilder output = new StringBuilder();
        for (byte value : digest.digest()) output.append(String.format("%02x", value & 255));
        return output.toString();
    }
    JSONObject envelope(byte[] bytes, String domain) throws Exception {
        if (bytes.length > ENVELOPE_LIMIT) throw new Failure("PACKAGE_INVALID", "签名清单超过限制");
        try {
            JSONObject wrapper = ContentJson.parse(new String(bytes, StandardCharsets.UTF_8));
            if (integer(wrapper, "envelope_version", 1, 1) != 1 || !wrapper.get("algorithm").equals("SHA256withECDSA")) throw new Exception();
            String keyId = string(wrapper, "key_id", 100);
            String key = config.getJSONObject("keys").getString(keyId);
            byte[] payload = base64(string(wrapper, "payload_b64", ENVELOPE_LIMIT));
            byte[] signature = base64(string(wrapper, "signature_b64", 256));
            Signature verifier = Signature.getInstance("SHA256withECDSA");
            verifier.initVerify(KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(base64(key))));
            verifier.update((domain + "\n").getBytes(StandardCharsets.US_ASCII));
            verifier.update(payload);
            if (!verifier.verify(signature)) throw new Exception();
            return ContentJson.parse(new String(payload, StandardCharsets.UTF_8));
        } catch (Exception error) {
            throw new Failure("SIGNATURE_INVALID", "内容签名无效，未安装或更新任何剧本");
        }
    }
    JSONObject catalog(byte[] bytes) throws Exception {
        JSONObject payload = envelope(bytes, "MMG-CATALOG-V1");
        if (!payload.getString("kind").equals("murder-mystery-catalog") || !payload.getString("publisher").equals(config.getString("publisher"))
            || !payload.getString("channel").equals("stable")) throw new Failure("PACKAGE_INVALID", "官方目录来源无效");
        integer(payload, "catalog_format", 1, 1);
        integer(payload, "catalog_revision", 1, Integer.MAX_VALUE);
        if (!string(payload, "issued_at", 60).matches("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,9})?(Z|[+-][0-9]{2}:[0-9]{2})")) throw new Failure("PACKAGE_INVALID", "目录时间无效");
        JSONArray entries = payload.getJSONArray("entries");
        if (entries.length() > 2000) throw new Failure("PACKAGE_INVALID", "目录条目超过限制");
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < entries.length(); i++) {
            JSONObject entry = entries.getJSONObject(i);
            if (!ids.add(id(entry, "story_id"))) throw new Failure("PACKAGE_INVALID", "目录剧本 ID 重复");
            integer(entry, "content_version", 1, Integer.MAX_VALUE);
            integer(entry, "min_engine_version", 1, Integer.MAX_VALUE);
            integer(entry, "bundle_format", 1, Integer.MAX_VALUE);
            integer(entry, "package_format", 1, Integer.MAX_VALUE);
            integer(entry, "num_characters", 1, 1000);
            integer(entry, "estimated_minutes", 5, 600);
            integer(entry, "bytes", 1, ZIP_LIMIT);
            for (String field : new String[]{"title", "summary", "author", "license", "difficulty"}) string(entry, field, 300);
            if (entry.has("release_notes")) string(entry, "release_notes", 2000);
            String state = string(entry, "status", 16);
            if (!state.equals("active") && !state.equals("withdrawn")) throw new Failure("PACKAGE_INVALID", "目录状态无效");
            hash(entry, "sha256");
            JSONArray urls = entry.getJSONArray("download_urls");
            if (urls.length() < 1 || urls.length() > 3) throw new Failure("PACKAGE_INVALID", "下载地址数量无效");
            for (int j = 0; j < urls.length(); j++) allowedUrl(urls.getString(j));
        }
        return payload;
    }
    private byte[] base64(String value) throws Exception {
        if (!value.matches("[A-Za-z0-9+/]+={0,2}") || value.length() % 4 != 0) throw new Exception("Base64 无效");
        return decoder.decode(value);
    }
    void allowedUrl(String address) throws Exception {
        java.net.URI uri = new java.net.URI(address);
        if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getRawUserInfo() != null
            || uri.getFragment() != null || (uri.getPort() != -1 && uri.getPort() != 443)) throw new Failure("PACKAGE_INVALID", "内容下载地址无效");
        JSONArray hosts = config.getJSONArray("allowed_hosts");
        for (int i = 0; i < hosts.length(); i++) if (hosts.getString(i).equals(uri.getHost())) return;
        throw new Failure("PACKAGE_INVALID", "内容下载主机未被允许");
    }
    static boolean compatible(JSONObject entry) throws Exception {
        return integer(entry, "min_engine_version", 1, Integer.MAX_VALUE) <= ENGINE_VERSION
            && integer(entry, "bundle_format", 1, Integer.MAX_VALUE) == 1 && integer(entry, "package_format", 1, Integer.MAX_VALUE) == 1
            && integer(entry, "num_characters", 1, 1000) >= 3 && entry.getInt("num_characters") <= 8;
    }
    JSONObject extract(File file, File directory) throws Exception {
        if (file.length() > ZIP_LIMIT) throw new Failure("PACKAGE_INVALID", "内容包不能超过 20 MiB");
        inspectDirectory(file);
        try (ZipFile archive = new ZipFile(file)) {
            ZipEntry manifestEntry = archive.getEntry("bundle.json");
            if (manifestEntry == null) throw new Failure("PACKAGE_INVALID", "缺少签名包清单");
            byte[] signed = readLimited(archive.getInputStream(manifestEntry), ENVELOPE_LIMIT);
            JSONObject manifest = envelope(signed, "MMG-BUNDLE-V1");
            if (!manifest.getString("kind").equals("murder-mystery-story-bundle") || !manifest.getString("publisher").equals(config.getString("publisher"))) throw new Failure("PACKAGE_INVALID", "内容包来源无效");
            integer(manifest, "bundle_format", 1, 1); integer(manifest, "package_format", 1, 1);
            id(manifest, "story_id"); integer(manifest, "content_version", 1, Integer.MAX_VALUE);
            if (integer(manifest, "min_engine_version", 1, Integer.MAX_VALUE) > ENGINE_VERSION) throw new Failure("ENGINE_UNSUPPORTED", "请更新应用后再安装此剧本");
            if (!string(manifest, "source_commit", 40).matches("[a-f0-9]{40}") || manifest.getString("source_commit").matches("0{40}")) throw new Failure("PACKAGE_INVALID", "内容来源提交无效");
            JSONArray rows = manifest.getJSONArray("files");
            if (rows.length() < 3 || rows.length() > 63) throw new Failure("PACKAGE_INVALID", "内容文件数量无效");
            Map<String, JSONObject> expected = new HashMap<>();
            for (int i = 0; i < rows.length(); i++) {
                JSONObject row = rows.getJSONObject(i); String name = string(row, "path", 150);
                if (!name.matches("package\\.json|LICENSE|SOURCE\\.txt|images/[A-Za-z0-9_-]+\\.webp") || expected.put(name, row) != null) throw new Failure("PACKAGE_INVALID", "内容文件路径无效或重复");
                integer(row, "bytes", 1, name.startsWith("images/") ? 4 * 1024 * 1024 : ENVELOPE_LIMIT);
                hash(row, "sha256");
            }
            if (!expected.keySet().containsAll(java.util.Arrays.asList("package.json", "LICENSE", "SOURCE.txt"))) throw new Failure("PACKAGE_INVALID", "缺少正文或来源许可");
            var entries = archive.entries(); Set<String> seen = new HashSet<>(); long total = 0;
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement(); String name = entry.getName();
                if (!seen.add(name)) throw new Failure("PACKAGE_INVALID", "ZIP 路径重复");
                if (entry.isDirectory()) {
                    if (!name.equals("images/")) throw new Failure("PACKAGE_INVALID", "ZIP 目录无效");
                    continue;
                }
                if (name.equals("bundle.json")) continue;
                JSONObject row = expected.get(name);
                if (row == null) throw new Failure("PACKAGE_INVALID", "包包含未声明文件");
                int limit = row.getInt("bytes");
                File target = new File(directory, name);
                if (!target.getCanonicalPath().startsWith(directory.getCanonicalPath() + File.separator)) throw new Failure("PACKAGE_INVALID", "文件路径越界");
                target.getParentFile().mkdirs(); MessageDigest digest = MessageDigest.getInstance("SHA-256"); long count = 0;
                try (InputStream input = archive.getInputStream(entry); FileOutputStream output = new FileOutputStream(target)) {
                    byte[] buffer = new byte[8192]; int size;
                    while ((size = input.read(buffer)) != -1) {
                        count += size; total += size;
                        if (count > limit || total > 40 * 1024 * 1024) throw new Failure("PACKAGE_INVALID", "展开内容超过限制");
                        output.write(buffer, 0, size); digest.update(buffer, 0, size);
                    }
                    output.getFD().sync();
                }
                StringBuilder value = new StringBuilder();
                for (byte b : digest.digest()) value.append(String.format("%02x", b & 255));
                if (count != limit || !value.toString().equals(row.getString("sha256"))) throw new Failure("HASH_MISMATCH", "内容文件校验失败");
            }
            if (!seen.containsAll(expected.keySet())) throw new Failure("PACKAGE_INVALID", "内容文件缺失");
            return manifest;
        }
    }
    static byte[] readLimited(InputStream input, int limit) throws Exception {
        try (InputStream stream = input; var output = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int size;
            while ((size = stream.read(buffer)) != -1) {
                if (output.size() + size > limit) throw new Failure("PACKAGE_INVALID", "内容超过大小限制");
                output.write(buffer, 0, size);
            }
            return output.toByteArray();
        }
    }
    private static long little(RandomAccessFile file, int count) throws Exception {
        long value = 0; for (int i = 0; i < count; i++) value |= (long)file.readUnsignedByte() << (8 * i); return value;
    }
    /** Central-directory flags/modes aren't exposed by Java ZipEntry. */
    private static void inspectDirectory(File source) throws Exception {
        try (RandomAccessFile file = new RandomAccessFile(source, "r")) {
            long end = -1;
            for (long offset = file.length() - 22; offset >= Math.max(0, file.length() - 65557); offset--) {
                file.seek(offset); if (little(file, 4) == 0x06054b50L) { end = offset; break; }
            }
            if (end < 0) throw new Failure("PACKAGE_INVALID", "ZIP 尾部无效");
            file.seek(end + 4);
            if (little(file, 2) != 0 || little(file, 2) != 0) throw new Failure("PACKAGE_INVALID", "不支持分卷 ZIP");
            int count = (int)little(file, 2), countTotal = (int)little(file, 2);
            long size = little(file, 4), start = little(file, 4), comment = little(file, 2);
            if (count != countTotal || count < 4 || count > 64 || start + size != end || end + 22 + comment != file.length()) throw new Failure("PACKAGE_INVALID", "ZIP 文件数量或结构无效");
            file.seek(start);
            for (int i = 0; i < count; i++) {
                long position = file.getFilePointer();
                if (little(file, 4) != 0x02014b50L) throw new Failure("PACKAGE_INVALID", "ZIP 索引无效");
                little(file, 2); little(file, 2);
                if ((little(file, 2) & 0x41) != 0) throw new Failure("PACKAGE_INVALID", "不支持加密 ZIP");
                file.seek(position + 28);
                int name = (int)little(file, 2), extra = (int)little(file, 2), note = (int)little(file, 2);
                if (name > 150 || little(file, 2) != 0) throw new Failure("PACKAGE_INVALID", "ZIP 文件名无效");
                little(file, 2); long attributes = little(file, 4);
                int mode = (int)((attributes >> 16) & 0xf000);
                if (mode != 0 && mode != 0x8000 && mode != 0x4000) throw new Failure("PACKAGE_INVALID", "ZIP 包含链接或特殊文件");
                long next = position + 46L + name + extra + note;
                if (next > end) throw new Failure("PACKAGE_INVALID", "ZIP 索引越界");
                file.seek(next);
            }
            if (file.getFilePointer() != end) throw new Failure("PACKAGE_INVALID", "ZIP 索引长度无效");
        }
    }
}
