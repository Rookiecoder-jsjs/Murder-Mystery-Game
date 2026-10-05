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
    private final Object preparationLock = new Object();
    private boolean prepared;
    static synchronized EngineHost get(Context context) {
        if (instance == null) instance = new EngineHost(context.getApplicationContext());
        return instance;
    }
    private EngineHost(Context context) {
        this.context = context;
        vault = new ModelVault(context);
        transport = new NativeTransport(vault);
    }
    void prepareAssets() throws Exception {
        synchronized (preparationLock) {
            if (prepared) return;
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
            File legacy = new File(bundled, "legacy-catalog");
            legacy.mkdirs();
            File[] oldFiles = catalog.listFiles((dir, name) -> name.endsWith(".json") && !name.equals("manifest.json"));
            if (oldFiles != null) for (File old : oldFiles) {
                File backup = new File(legacy, old.getName());
                if (!backup.exists()) {
                    File temporary = File.createTempFile("legacy-", ".tmp", legacy);
                    try {
                        try (var input = new java.io.FileInputStream(old);
                             var output = new FileOutputStream(temporary)) {
                            byte[] buffer = new byte[8192]; int count;
                            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                            output.getFD().sync();
                        }
                        if (!temporary.renameTo(backup)) throw new java.io.IOException("旧剧本备份失败");
                        StoryLibraryHost.syncDirectory(legacy);
                    } finally { temporary.delete(); }
                }
            }
            // Always replace bundled package files; the manifest chooses current
            // versions. Active sessions keep their own embedded story snapshot.
            for (String name : context.getAssets().list("stories/catalog")) {
                File temporary = File.createTempFile("base-", ".tmp", catalog);
                try (var input = context.getAssets().open("stories/catalog/" + name);
                     var output = new FileOutputStream(temporary)) {
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                    output.getFD().sync();
                }
                if (!temporary.renameTo(new File(catalog, name))) throw new java.io.IOException("基础内容安装失败");
            }
            StoryLibraryHost.syncDirectory(catalog);
            prepared = true;
        }
    }
    synchronized String command(String json) throws Exception {
        if (runtime == null) {
            prepareAssets();
            File directory = new File(context.getFilesDir(), "game");
            File bundled = new File(context.getFilesDir(), "bundled-stories");
            PyObject candidate = Python.getInstance().getModule("mobile_runtime");
            candidate.callAttr("initialize", directory.getAbsolutePath(), bundled.getAbsolutePath(), transport);
            runtime = candidate;
        }
        return runtime.callAttr("command", json).toString();
    }
}
