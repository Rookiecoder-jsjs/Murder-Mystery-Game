package com.murdermystery.game;

import org.json.JSONObject;
import java.net.URL;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

/** Called by embedded Python workers. Never called on the Android main thread. */
public final class NativeTransport {
    private final ModelVault vault;
    private volatile boolean active = true;
    NativeTransport(ModelVault vault) { this.vault = vault; }
    public boolean isActive() { return active; }
    public void setActive(boolean value) { active = value; }
    public String settings() throws Exception { return vault.settings().toString(); }

    public String complete(String body, double timeout, String baseUrl) {
        HttpsURLConnection connection = null;
        try {
            if (!active) return error("应用已切到后台，请回到前台继续");
            String key;
            try { key = vault.keyFor(baseUrl); }
            catch (IllegalArgumentException mismatch) { return error(mismatch.getMessage()); }
            if (key.isEmpty()) return error("请先在模型设置中填写 API key");
            connection = (HttpsURLConnection) new URL(baseUrl.replaceAll("/+$", "") + "/chat/completions").openConnection();
            connection.setRequestMethod("POST");
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(30000);
            connection.setReadTimeout((int) (Math.min(300, Math.max(10, timeout)) * 1000));
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + key);
            connection.setDoOutput(true);
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(bytes.length);
            try (var stream = connection.getOutputStream()) { stream.write(bytes); }
            int status = connection.getResponseCode();
            if (status != 200) {
                if (status == 401 || status == 403) return error("密钥无效或没有模型访问权限，请检查模型设置");
                if (status == 402 || status == 429) return error("模型额度不足或请求过于频繁，请稍后继续");
                return error("模型服务返回错误（HTTP " + status + "），请检查地址和模型名称");
            }
            try (InputStream stream = connection.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = stream.read(buffer)) != -1) {
                    if (output.size() + n > 8 * 1024 * 1024) return error("模型响应超过容量限制");
                    output.write(buffer, 0, n);
                }
                return output.toString(StandardCharsets.UTF_8.name());
            }
        } catch (Exception error) {
            return error("模型连接中断或超时；结果可能已产生，请检查网络后手动继续");
        } finally { if (connection != null) connection.disconnect(); }
    }

    private String error(String message) {
        try { return new JSONObject().put("error", message).toString(); }
        catch (Exception ignored) { return "{\"error\":\"模型请求失败\"}"; }
    }
}
