package com.murdermystery.game;

import android.content.Context;
import android.content.pm.ActivityInfo;
import android.content.ComponentName;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.chaquo.python.Python;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.ByteArrayOutputStream;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class NativeEngineTest {
    @Test public void bundledEngineAndPortraitShellWorkWithoutServer() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        EngineHost host = EngineHost.get(context);
        JSONObject stories = new JSONObject(host.command("{\"kind\":\"read\",\"endpoint\":\"/stories\"}"));
        assertTrue(stories.toString(), stories.getJSONObject("data").getJSONArray("stories").length() > 0);
        JSONObject games = new JSONObject(host.command("{\"kind\":\"games\"}"));
        assertTrue(games.has("data"));
        JSONObject settings = host.vault.settings();
        assertFalse(settings.has("apiKey"));
        assertFalse(settings.has("key"));
        assertEquals(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT, context.getPackageManager()
            .getActivityInfo(new ComponentName(context, MainActivity.class), 0).screenOrientation);
        JSONObject proof = new JSONObject(Python.getInstance().getModule("probe")
            .callAttr("run", context.getCacheDir().getAbsolutePath()).toString());
        assertTrue(proof.getBoolean("ok"));
        try (var input = context.getAssets().open("public/index.html"); var output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            String html = output.toString("UTF-8");
            assertFalse(html.contains("fonts.googleapis.com"));
            assertFalse(html.contains("fonts.gstatic.com"));
        }
        try (var input = context.getAssets().open("capacitor.config.json"); var output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            assertFalse(new JSONObject(output.toString("UTF-8")).getJSONObject("server").has("url"));
        }
    }
}
