package com.murdermystery.game;

import android.content.Context;
import com.chaquo.python.Python;
import com.chaquo.python.PyObject;
import com.chaquo.python.android.AndroidPlatform;
import java.io.File;
import java.io.FileOutputStream;

/** Process-scoped host, independent of Activity/WebView recreation. */
final class EngineHost {
    private static EngineHost instance;
    final ModelVault vault;
    final NativeTransport transport;
    private PyObject runtime;
    private final Context context;
    static synchronized EngineHost get(Context context) {
        if (instance == null) instance = new EngineHost(context.getApplicationContext());
        return instance;
    }
    private EngineHost(Context context) {
        this.context = context;
        vault = new ModelVault(context);
        transport = new NativeTransport(vault);
    }
    synchronized String command(String json) throws Exception {
        if (runtime == null) {
            synchronized (Python.class) {
                if (!Python.isStarted()) Python.start(new AndroidPlatform(context));
            }
            File directory = new File(context.getFilesDir(), "game");
            File bundled = new File(context.getFilesDir(), "bundled-stories");
            directory.mkdirs(); bundled.mkdirs();
            for (String name : context.getAssets().list("stories")) {
                if (name.equals("catalog")) continue;
                try (var input = context.getAssets().open("stories/" + name);
                     var output = new FileOutputStream(new File(bundled, name))) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                }
            }
            File catalog = new File(bundled, "catalog");
            catalog.mkdirs();
            // Always replace bundled package files; the manifest chooses current
            // versions. Active sessions keep their own embedded story snapshot.
            for (String name : context.getAssets().list("stories/catalog")) {
                try (var input = context.getAssets().open("stories/catalog/" + name);
                     var output = new FileOutputStream(new File(catalog, name))) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                }
            }
            PyObject candidate = Python.getInstance().getModule("mobile_runtime");
            candidate.callAttr("initialize", directory.getAbsolutePath(), bundled.getAbsolutePath(), transport);
            runtime = candidate;
        }
        return runtime.callAttr("command", json).toString();
    }
}
