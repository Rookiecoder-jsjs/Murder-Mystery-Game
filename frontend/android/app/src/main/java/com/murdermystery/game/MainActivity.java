package com.murdermystery.game;

import com.getcapacitor.BridgeActivity;
import android.os.Bundle;
import android.util.Log;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class MainActivity extends BridgeActivity {
    @Override public void onCreate(Bundle state) {
        registerPlugin(GameEnginePlugin.class);
        super.onCreate(state);
        if (BuildConfig.DEBUG) new Thread(() -> {
            try {
                synchronized (Python.class) {
                    if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                }
                Log.i("MysteryProbe", Python.getInstance().getModule("probe")
                    .callAttr("run", getFilesDir().getAbsolutePath()).toString());
            } catch (Exception error) { Log.e("MysteryProbe", "Embedding failed", error); }
        }, "embedding-probe").start();
    }
}
