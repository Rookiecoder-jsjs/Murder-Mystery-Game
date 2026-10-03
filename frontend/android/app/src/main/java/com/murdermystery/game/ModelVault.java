package com.murdermystery.game;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import java.security.KeyStore;
import java.net.URI;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Credentials remain in the native process; JS only sees settings and a boolean. */
final class ModelVault {
    private static final String ALIAS = "mystery-model-credential-v1";
    private final SharedPreferences prefs;
    ModelVault(Context context) { prefs = context.getSharedPreferences("model-v1", Context.MODE_PRIVATE); }

    private SecretKey encryptionKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }

    synchronized String key() throws Exception {
        String encrypted = prefs.getString("ciphertext", "");
        if (encrypted.isEmpty()) return "";
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, encryptionKey(), new GCMParameterSpec(128,
            Base64.decode(prefs.getString("iv", ""), Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP)), java.nio.charset.StandardCharsets.UTF_8);
    }

    synchronized String keyFor(String baseUrl) throws Exception {
        // Snapshot the destination and credential under one lock. A concurrent
        // settings save must never pair the new service's key with the old URL.
        if (!baseUrl.equals(settings().getString("baseUrl")))
            throw new IllegalArgumentException("此任务使用原来的模型服务，请恢复原服务地址后继续");
        return key();
    }

    synchronized JSONObject settings() throws Exception {
        return new JSONObject().put("baseUrl", prefs.getString("baseUrl", "https://api.deepseek.com/v1"))
            .put("storyModel", prefs.getString("storyModel", "deepseek-v4-pro"))
            .put("roleModel", prefs.getString("roleModel", "deepseek-v4-flash"))
            .put("reviewModel", prefs.getString("reviewModel", "deepseek-v4-pro"))
            .put("thinking", prefs.getBoolean("thinking", true))
            .put("configured", prefs.contains("ciphertext"));
    }

    synchronized void save(String base, String story, String role, String review, String key, boolean thinking) throws Exception {
        base = base.trim().replaceAll("/+$", "");
        URI uri = new URI(base);
        if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null
            || uri.getQuery() != null || uri.getFragment() != null) throw new IllegalArgumentException("模型地址必须是有效的 HTTPS API 地址");
        if (story.trim().isEmpty() || role.trim().isEmpty() || review.trim().isEmpty())
            throw new IllegalArgumentException("请填写三个模型名称（可以相同）");
        if (!base.equals(settings().getString("baseUrl")) && key.trim().isEmpty())
            throw new IllegalArgumentException("更换服务地址时请重新填写密钥");
        SharedPreferences.Editor edit = prefs.edit().putString("baseUrl", base)
            .putString("storyModel", story.trim()).putString("roleModel", role.trim())
            .putString("reviewModel", review.trim()).putBoolean("thinking", thinking);
        if (!key.trim().isEmpty()) {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, encryptionKey());
            edit.putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP));
            edit.putString("ciphertext", Base64.encodeToString(cipher.doFinal(key.trim().getBytes(java.nio.charset.StandardCharsets.UTF_8)), Base64.NO_WRAP));
        }
        if (!edit.commit()) throw new IllegalStateException("配置保存失败");
    }
}
