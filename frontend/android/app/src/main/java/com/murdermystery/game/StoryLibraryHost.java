package com.murdermystery.game;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.system.Os;
import android.system.OsConstants;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONArray;
import org.json.JSONObject;

/** Process-owned content queue, independent of game commands and model keys. */
final class StoryLibraryHost {
    private static StoryLibraryHost instance;
    static synchronized StoryLibraryHost get(Context context) throws Exception {
        if (instance == null) instance = new StoryLibraryHost(context.getApplicationContext());
        return instance;
    }
    final File root;
    private final File personal;
    private final JSONObject config;
    private final ContentVerifier verifier;
    private final PyObject content;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Map<String, Task> tasks = new ConcurrentHashMap<>();
    private volatile JSONObject catalog;
    private volatile long lastChecked;
    private volatile String lastCheckError = "";

    private StoryLibraryHost(Context context) throws Exception {
        EngineHost.get(context).prepareAssets();
        root = new File(context.getFilesDir(), "story-library");
        personal = new File(context.getFilesDir(), "game/stories");
        root.mkdirs(); new File(root, "tasks").mkdirs();
        config = ContentJson.parse(new String(ContentVerifier.readLimited(context.getAssets().open("story-library-config.json"),
            ContentVerifier.ENVELOPE_LIMIT), StandardCharsets.UTF_8));
        verifier = new ContentVerifier(config);
        verifier.allowedUrl(config.getString("catalog_url"));
        JSONArray mirrors = config.optJSONArray("catalog_urls");
        if (mirrors != null) for (int i = 0; i < mirrors.length(); i++) verifier.allowedUrl(mirrors.getString(i));
        content = Python.getInstance().getModule("mobile_content");
        content.callAttr("configure", root.getAbsolutePath(), new File(context.getFilesDir(), "bundled-stories").getAbsolutePath());
        File cached = new File(root, "catalog/cache.json");
        if (cached.exists()) {
            try {
                JSONObject cache = readJson(cached, 3 * ContentVerifier.ENVELOPE_LIMIT);
                catalog = verifier.catalog(cache.getJSONObject("envelope").toString().getBytes(StandardCharsets.UTF_8));
                lastChecked = cache.getLong("last_checked_at");
            } catch (Exception error) { lastCheckError = "本地目录缓存未通过校验，请重新检查更新"; }
        }
        File[] records = new File(root, "tasks").listFiles((dir, name) -> name.matches("[a-f0-9-]{36}\\.json"));
        if (records != null) for (File record : records) {
            try {
                Task task = new Task(readJson(record, 65536));
                if (!task.terminal()) {
                    boolean installed = !task.storyId.isEmpty() && !task.digest.isEmpty()
                        && content.callAttr("is_installed", task.storyId, task.version, task.digest).toBoolean();
                    task.state = installed ? "complete" : "interrupted";
                    task.errorCode = installed ? "" : "INTERRUPTED";
                    task.error = installed ? "" : task.kind.equals("check") ? "上次目录检查中断，请重新检查更新" : "应用上次运行被中断，请重试下载；已有剧本仍可游玩";
                    save(task);
                }
                tasks.put(task.id, task);
            } catch (Exception ignored) { /* Corrupt task files can't hide installed content. */ }
        }
    }

    private static final class Cancelled extends Exception {}
    private static final class Task {
        final String id, kind;
        final long created;
        String state = "queued", storyId = "", digest = "", error = "", errorCode = "";
        int version;
        long downloaded, total;
        volatile boolean cancelled, committing;
        volatile HttpsURLConnection connection;
        volatile InputStream input;
        Task(String kind) { this.id = UUID.randomUUID().toString(); this.kind = kind; created = System.currentTimeMillis(); }
        Task(JSONObject json) throws Exception {
            id = ContentVerifier.id(json, "id"); kind = json.getString("kind"); created = json.getLong("created");
            state = json.getString("state"); storyId = json.optString("story_id", ""); digest = json.optString("sha256", "");
            version = json.optInt("content_version", 0); downloaded = json.optLong("downloaded_bytes");
            total = json.optLong("total_bytes"); error = json.optString("error", ""); errorCode = json.optString("error_code", "");
        }
        synchronized boolean terminal() { return java.util.Arrays.asList("complete", "failed", "cancelled", "interrupted").contains(state); }
        synchronized JSONObject view() throws Exception {
            return new JSONObject().put("id", id).put("kind", kind).put("created", created).put("state", state)
                .put("story_id", storyId).put("content_version", version).put("sha256", digest)
                .put("downloaded_bytes", downloaded).put("total_bytes", total).put("error", error).put("error_code", errorCode)
                .put("can_cancel", !terminal() && !committing);
        }
    }
    private static JSONObject readJson(File source, int limit) throws Exception {
        return ContentJson.parse(new String(ContentVerifier.readLimited(new java.io.FileInputStream(source), limit), StandardCharsets.UTF_8));
    }
    static void atomicJson(File path, JSONObject data) throws Exception {
        path.getParentFile().mkdirs();
        File temporary = File.createTempFile("write-", ".tmp", path.getParentFile());
        try {
            try (FileOutputStream output = new FileOutputStream(temporary)) {
                output.write(data.toString().getBytes(StandardCharsets.UTF_8)); output.getFD().sync();
            }
            if (!temporary.renameTo(path)) throw new java.io.IOException("本地文件提交失败");
            syncDirectory(path.getParentFile());
        } finally { temporary.delete(); }
    }
    static void syncDirectory(File directory) throws Exception {
        var descriptor = Os.open(directory.getAbsolutePath(), OsConstants.O_RDONLY, 0);
        try { Os.fsync(descriptor); } finally { Os.close(descriptor); }
    }
    private void save(Task task) throws Exception { synchronized (task) { atomicJson(new File(root, "tasks/" + task.id + ".json"), task.view()); } }
    private void stage(Task task, String state) throws Exception {
        synchronized (task) { if (task.cancelled) throw new Cancelled(); task.state = state; save(task); }
    }
    private Task add(String kind) throws Exception {
        Task task = new Task(kind); save(task); tasks.put(task.id, task); return task;
    }

    JSONObject read() throws Exception {
        JSONObject local = ContentJson.parse(content.callAttr("state").toString());
        Map<String, JSONObject> available = new HashMap<>();
        JSONObject current = catalog;
        if (current != null) {
            JSONArray entries = current.getJSONArray("entries");
            for (int i = 0; i < entries.length(); i++) {
                JSONObject entry = entries.getJSONObject(i);
                if (entry.getString("status").equals("active")) available.put(entry.getString("story_id"), entry);
            }
        }
        JSONArray books = new JSONArray(), installed = local.getJSONArray("stories");
        for (int i = 0; i < installed.length(); i++) {
            JSONObject book = installed.getJSONObject(i);
            book.put("installed_version", book.getInt("version"));
            decorate(book, available.remove(book.getString("id"))); books.put(book);
        }
        for (JSONObject entry : available.values()) {
            JSONObject book = publicEntry(entry);
            book.put("installed_version", JSONObject.NULL); decorate(book, entry); books.put(book);
        }
        ArrayList<Task> sorted = new ArrayList<>(tasks.values());
        sorted.sort(Comparator.comparingLong((Task task) -> task.created).reversed());
        JSONArray activity = new JSONArray();
        for (Task task : sorted.subList(0, Math.min(30, sorted.size()))) activity.put(task.view());
        return new JSONObject().put("books", books).put("tasks", activity).put("library_revision", local.getLong("library_revision"))
            .put("last_checked_at", lastChecked == 0 ? JSONObject.NULL : lastChecked)
            .put("last_check_error", lastCheckError).put("catalog_revision", current == null ? 0 : current.getInt("catalog_revision"))
            .put("source_url", "https://github.com/" + config.getString("publisher") + "/tree/" + BuildConfig.SOURCE_COMMIT);
    }
    private JSONObject publicEntry(JSONObject entry) throws Exception {
        JSONObject book = new JSONObject().put("id", entry.getString("story_id")).put("origin", "builtin").put("topic", "").put("created_at", "");
        for (String key : new String[]{"title", "summary", "num_characters", "difficulty", "estimated_minutes", "author", "license"}) book.put(key, entry.get(key));
        book.put("version", entry.get("content_version")); return book;
    }
    private void decorate(JSONObject book, JSONObject entry) throws Exception {
        if (entry == null) {
            book.put("latest_version", book.optInt("version", 1)).put("can_download", false).put("compatible", true);
            return;
        }
        book.put("available", publicEntry(entry)).put("latest_version", entry.getInt("content_version"))
            .put("sha256", entry.getString("sha256")).put("download_bytes", entry.getInt("bytes"))
            .put("release_notes", entry.optString("release_notes", "")).put("compatible", ContentVerifier.compatible(entry))
            .put("can_download", ContentVerifier.compatible(entry) && (book.isNull("installed_version") || entry.getInt("content_version") > book.getInt("installed_version")));
    }

    synchronized JSONObject check() throws Exception {
        for (Task existing : tasks.values()) if (existing.kind.equals("check") && !existing.terminal()) return existing.view();
        Task task = add("check");
        worker.execute(() -> run(task, () -> {
            stage(task, "checking");
            byte[] bytes = downloadCatalog(task);
            JSONObject fresh = verifier.catalog(bytes);
            JSONObject old = catalog;
            if (old != null && (fresh.getInt("catalog_revision") < old.getInt("catalog_revision")
                || (fresh.getInt("catalog_revision") == old.getInt("catalog_revision") && !ContentVerifier.hex(payload(bytes)).equals(ContentVerifier.hex(payloadEnvelope(old)))))) {
                throw new ContentVerifier.Failure("VERSION_CONFLICT", "目录版本发生回退或同版本内容不同，已保留原目录");
            }
            synchronized (task) {
                if (task.cancelled) throw new Cancelled(); task.committing = true;
            }
            long now = System.currentTimeMillis();
            atomicJson(new File(root, "catalog/cache.json"), new JSONObject().put("envelope", ContentJson.parse(new String(bytes, StandardCharsets.UTF_8))).put("last_checked_at", now));
            catalog = fresh; lastChecked = now; lastCheckError = "";
        }));
        return task.view();
    }
    private static byte[] payload(byte[] bytes) throws Exception {
        return android.util.Base64.decode(ContentJson.parse(new String(bytes, StandardCharsets.UTF_8)).getString("payload_b64"), android.util.Base64.DEFAULT);
    }
    // Preserve the verified raw payload hash, not a reserialized JSONObject hash.
    private byte[] payloadEnvelope(JSONObject ignored) throws Exception {
        return payload(readJson(new File(root, "catalog/cache.json"), 3 * ContentVerifier.ENVELOPE_LIMIT).getJSONObject("envelope").toString().getBytes(StandardCharsets.UTF_8));
    }
    synchronized JSONObject install(JSONObject request) throws Exception {
        String id = ContentVerifier.id(request, "story_id"), digest = ContentVerifier.hash(request, "expected_sha256");
        int version = ContentVerifier.integer(request, "content_version", 1, Integer.MAX_VALUE);
        JSONObject candidate = null, current = catalog;
        if (current != null) for (int i = 0; i < current.getJSONArray("entries").length(); i++) {
            JSONObject entry = current.getJSONArray("entries").getJSONObject(i);
            if (entry.getString("story_id").equals(id)) candidate = entry;
        }
        if (candidate == null || !candidate.getString("status").equals("active") || candidate.getInt("content_version") != version
            || !candidate.getString("sha256").equals(digest)) throw new ContentVerifier.Failure("VERSION_CONFLICT", "目录已变化，请检查更新后重试");
        if (!ContentVerifier.compatible(candidate)) throw new ContentVerifier.Failure("ENGINE_UNSUPPORTED", "此剧本需要更新应用");
        for (Task existing : tasks.values()) if (existing.storyId.equals(id) && !existing.terminal()) return existing.view();
        Task task = add("install"); task.storyId = id; task.version = version; task.digest = digest; task.total = candidate.getInt("bytes"); save(task);
        if (content.callAttr("is_installed", id, version, digest).toBoolean()) {
            task.state = "complete"; save(task); return task.view();
        }
        final JSONObject selected = candidate;
        worker.execute(() -> run(task, () -> {
            File staging = new File(root, "staging/" + task.id); staging.mkdirs();
            if (root.getUsableSpace() < selected.getInt("bytes") + 40L * 1024 * 1024 + 8L * 1024 * 1024) throw new ContentVerifier.Failure("NO_SPACE", "手机可用空间不足，请清理空间后重试");
            stage(task, "downloading"); File zip = new File(staging, "source.mmstory");
            downloadFile(selected.getJSONArray("download_urls").getString(0), zip, task, selected.getInt("bytes"));
            if (zip.length() != selected.getInt("bytes") || !ContentVerifier.fileHash(zip).equals(task.digest)) throw new ContentVerifier.Failure("HASH_MISMATCH", "下载内容不完整或校验失败，请重试");
            installZip(zip, staging, task, selected);
        }));
        return task.view();
    }
    JSONObject installFile(InputStream stream) throws Exception {
        Task task;
        try { task = add("file"); }
        catch (Exception error) { stream.close(); throw error; }
        task.input = stream;
        worker.execute(() -> run(task, () -> {
            try (InputStream input = stream) {
                File staging = new File(root, "staging/" + task.id); staging.mkdirs();
                if (root.getUsableSpace() < 68L * 1024 * 1024) throw new ContentVerifier.Failure("NO_SPACE", "手机可用空间不足");
                stage(task, "downloading"); File zip = new File(staging, "source.mmstory");
                copy(input, zip, task, ContentVerifier.ZIP_LIMIT, false);
                task.digest = ContentVerifier.fileHash(zip); save(task);
                installZip(zip, staging, task, null);
            }
        }));
        return task.view();
    }
    private void installZip(File zip, File staging, Task task, JSONObject entry) throws Exception {
        stage(task, "verifying"); File unpacked = new File(staging, "unpacked"); unpacked.mkdirs();
        JSONObject manifest = verifier.extract(zip, unpacked);
        if (entry != null && (!manifest.getString("story_id").equals(task.storyId) || manifest.getInt("content_version") != task.version
            || manifest.getInt("min_engine_version") != entry.getInt("min_engine_version"))) throw new ContentVerifier.Failure("PACKAGE_INVALID", "目录和内容包版本不一致");
        JSONObject info = ContentJson.parse(content.callAttr("validate", unpacked.getAbsolutePath(), task.digest).toString());
        task.storyId = manifest.getString("story_id"); task.version = manifest.getInt("content_version");
        if (!info.getString("id").equals(task.storyId) || info.getInt("version") != task.version) throw new ContentVerifier.Failure("PACKAGE_INVALID", "正文和清单版本不一致");
        if (entry != null) for (String key : new String[]{"title", "summary", "num_characters", "difficulty", "estimated_minutes", "author", "license"}) {
            if (!String.valueOf(info.get(key)).equals(String.valueOf(entry.get(key)))) throw new ContentVerifier.Failure("PACKAGE_INVALID", "目录介绍与正文不同");
        }
        File images = new File(unpacked, "images"); File[] artwork = images.listFiles();
        if (artwork != null) for (File image : artwork) {
            BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(image.getAbsolutePath(), options);
            if (options.outWidth < 1 || options.outHeight < 1 || (long)options.outWidth * options.outHeight > 16000000 || !"image/webp".equals(options.outMimeType)) throw new ContentVerifier.Failure("PACKAGE_INVALID", "配图格式或尺寸无效");
            Bitmap decoded = BitmapFactory.decodeFile(image.getAbsolutePath());
            if (decoded == null) throw new ContentVerifier.Failure("PACKAGE_INVALID", "配图文件损坏");
            decoded.recycle();
        }
        stage(task, "installing");
        atomicJson(new File(unpacked, "complete.json"), new JSONObject().put("story_id", task.storyId).put("version", task.version)
            .put("sha256", task.digest).put("fingerprint", info.getString("fingerprint")).put("min_engine_version", manifest.getInt("min_engine_version")));
        File destination = new File(root, "packs/" + task.storyId + "/v" + task.version + "-" + task.digest);
        destination.getParentFile().mkdirs();
        if (!destination.exists() && !unpacked.renameTo(destination)) throw new java.io.IOException("内容文件移动失败");
        syncDirectory(destination.getParentFile());
        syncDirectory(destination.getParentFile().getParentFile());
        syncDirectory(new File(root, "packs"));
        synchronized (task) { if (task.cancelled) throw new Cancelled(); task.committing = true; }
        content.callAttr("activate", task.storyId, task.version, task.digest, personal.getAbsolutePath());
    }
    synchronized JSONObject cancel(String id) throws Exception {
        Task task = tasks.get(id);
        if (task == null) throw new ContentVerifier.Failure("PACKAGE_INVALID", "下载任务不存在");
        synchronized (task) {
            if (task.terminal() || task.committing) return task.view();
            task.cancelled = true;
            if (task.connection != null) task.connection.disconnect();
            if (task.input != null) try { task.input.close(); } catch (java.io.IOException ignored) { /* Cancellation owns this stream. */ }
            if (task.state.equals("queued")) { task.state = "cancelled"; save(task); }
            return task.view();
        }
    }
    synchronized void remove(String id) throws Exception {
        if (!UUID.fromString(id).toString().equals(id)) throw new ContentVerifier.Failure("PACKAGE_INVALID", "剧本 ID 无效");
        for (Task task : tasks.values()) if (task.storyId.equals(id) && !task.terminal()) throw new ContentVerifier.Failure("VERSION_CONFLICT", "请先取消或等待此剧本的下载");
        content.callAttr("remove", id);
    }
    private interface Job { void run() throws Exception; }
    private void run(Task task, Job job) {
        try {
            if (task.cancelled) throw new Cancelled();
            job.run(); synchronized (task) { task.state = "complete"; task.error = ""; }
        } catch (Exception error) {
            synchronized (task) {
                String failedStage = task.state;
                task.state = task.cancelled && !task.committing ? "cancelled" : "failed";
                task.errorCode = error instanceof ContentVerifier.Failure ? ((ContentVerifier.Failure)error).code : "PACKAGE_INVALID";
                task.error = error instanceof ContentVerifier.Failure ? error.getMessage() : "内容检查或安装失败，已有剧本已保留";
                String message = String.valueOf(error.getMessage());
                if (message.contains("ID_CONFLICT:")) { task.errorCode = "ID_CONFLICT"; task.error = "个人剧本使用了相同 ID，已保留个人内容"; }
                if (message.contains("VERSION_CONFLICT:")) { task.errorCode = "VERSION_CONFLICT"; task.error = "内容版本冲突，已保留原版本"; }
                if (error instanceof java.io.IOException || message.contains("Errno 28")) {
                    boolean noSpace = message.contains("Errno 28") || root.getUsableSpace() < 8L * 1024 * 1024;
                    boolean network = task.kind.equals("check") || (task.kind.equals("install") && failedStage.equals("downloading"));
                    task.errorCode = noSpace ? "NO_SPACE" : network ? "CATALOG_UNAVAILABLE" : "PACKAGE_INVALID";
                    task.error = noSpace ? "手机空间不足，请清理后重试" : network ? "下载连接中断或超时，请检查网络后重试" : "内容包读取或写入失败，请重新选择或下载";
                }
                if (BuildConfig.DEBUG) android.util.Log.w("MysteryContent", task.errorCode + ": " + error.getClass().getSimpleName());
                if (task.state.equals("cancelled")) { task.error = "下载已取消"; task.errorCode = ""; }
                if (task.kind.equals("check")) lastCheckError = task.error;
            }
        } finally {
            if (task.input != null) {
                try { task.input.close(); } catch (java.io.IOException ignored) { /* Already closed or cancelled. */ }
                task.input = null;
            }
            if (!task.kind.equals("check") && !task.storyId.isEmpty() && !task.digest.isEmpty()) {
                try {
                    if (content.callAttr("is_installed", task.storyId, task.version, task.digest).toBoolean()) {
                        synchronized (task) { task.state = "complete"; task.error = ""; task.errorCode = ""; }
                    }
                } catch (Exception ignored) { /* Recover from the registry on next launch. */ }
            }
            try { save(task); } catch (Exception ignored) { /* Registry recovers an acknowledged install even if this write fails. */ }
            deleteTree(new File(root, "staging/" + task.id));
        }
    }
    private HttpsURLConnection open(String address, Task task, String accept) throws Exception {
        for (int redirects = 0; redirects < 6; redirects++) {
            if (task.cancelled) throw new Cancelled();
            verifier.allowedUrl(address);
            HttpsURLConnection connection = (HttpsURLConnection)new java.net.URL(address).openConnection();
            task.connection = connection;
            connection.setRequestMethod("GET"); connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(15000); connection.setReadTimeout(20000);
            connection.setRequestProperty("Accept", accept);
            connection.setRequestProperty("User-Agent", "Murder-Mystery-Story-Library/1");
            int status = connection.getResponseCode();
            if (status == 200) return connection;
            String location = connection.getHeaderField("Location"); connection.disconnect();
            if (java.util.Arrays.asList(301, 302, 303, 307, 308).contains(status) && location != null) {
                address = new java.net.URL(new java.net.URL(address), location).toString(); continue;
            }
            throw new java.io.IOException("内容服务暂不可用");
        }
        throw new ContentVerifier.Failure("PACKAGE_INVALID", "内容下载重定向次数过多");
    }
    private byte[] downloadCatalog(Task task) throws Exception {
        JSONArray addresses = config.optJSONArray("catalog_urls");
        if (addresses == null) addresses = new JSONArray().put(config.getString("catalog_url"));
        java.io.IOException last = null;
        for (int i = 0; i < addresses.length(); i++) {
            if (task.cancelled) throw new Cancelled();
            try { return downloadBytes(addresses.getString(i), task, ContentVerifier.ENVELOPE_LIMIT); }
            catch (java.io.IOException error) { last = error; }
        }
        if (last != null) throw last;
        throw new ContentVerifier.Failure("CATALOG_UNAVAILABLE", "官方目录地址尚未配置");
    }
    private byte[] downloadBytes(String url, Task task, int limit) throws Exception {
        // GitHub's official contents API can return the identical raw envelope.
        HttpsURLConnection connection = open(url, task, "application/vnd.github.raw+json");
        try { return ContentVerifier.readLimited(connection.getInputStream(), limit); }
        finally { connection.disconnect(); task.connection = null; }
    }
    private void downloadFile(String url, File file, Task task, int limit) throws Exception {
        HttpsURLConnection connection = open(url, task, "application/octet-stream");
        try (InputStream input = connection.getInputStream()) { copy(input, file, task, limit, true); }
        finally { connection.disconnect(); task.connection = null; }
    }
    private void copy(InputStream input, File file, Task task, int limit, boolean expected) throws Exception {
        long lastSave = 0;
        try (FileOutputStream output = new FileOutputStream(file)) {
            byte[] buffer = new byte[8192]; int count;
            while ((count = input.read(buffer)) != -1) {
                if (task.cancelled) throw new Cancelled();
                synchronized (task) {
                    task.downloaded += count;
                    if (task.downloaded > limit) throw new ContentVerifier.Failure("PACKAGE_INVALID", "下载超过声明大小限制");
                }
                output.write(buffer, 0, count);
                if (System.currentTimeMillis() - lastSave > 500) { save(task); lastSave = System.currentTimeMillis(); }
            }
            output.getFD().sync();
            if (expected && task.downloaded != limit) throw new ContentVerifier.Failure("HASH_MISMATCH", "下载文件不完整");
        }
    }
    private static void deleteTree(File file) {
        File[] children = file.listFiles(); if (children != null) for (File child : children) deleteTree(child);
        file.delete();
    }
}
