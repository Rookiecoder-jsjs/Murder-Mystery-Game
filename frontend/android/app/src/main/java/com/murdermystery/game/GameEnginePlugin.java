package com.murdermystery.game;

import android.app.AlertDialog;
import android.app.Activity;
import android.content.Intent;
import androidx.activity.result.ActivityResult;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.CheckBox;
import android.widget.Toast;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.ActivityCallback;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONObject;

@CapacitorPlugin(name = "GameEngine")
public class GameEnginePlugin extends Plugin {
    private static final ExecutorService bridgeWorker = Executors.newSingleThreadExecutor();
    private static final ExecutorService libraryControl = Executors.newSingleThreadExecutor();
    private EngineHost host;
    @Override public void load() { host = EngineHost.get(getContext()); }
    @Override protected void handleOnPause() { host.transport.setActive(false); }
    @Override protected void handleOnResume() { host.transport.setActive(true); }

    @PluginMethod public void libraryRead(PluginCall call) {
        libraryControl.execute(() -> {
            try { call.resolve(new JSObject(StoryLibraryHost.get(getContext()).read().toString())); }
            catch (Exception error) { call.reject("剧本库读取失败，请重新打开应用"); }
        });
    }
    @PluginMethod public void libraryCommand(PluginCall call) {
        libraryControl.execute(() -> {
            try {
                StoryLibraryHost library = StoryLibraryHost.get(getContext());
                String kind = call.getString("kind", "");
                JSONObject result;
                switch (kind) {
                    case "check": result = library.check(); break;
                    case "install": result = library.install(call.getObject("body", new JSObject())); break;
                    case "cancel": result = library.cancel(call.getString("id", "")); break;
                    case "remove": library.remove(call.getString("storyId", "")); result = new JSONObject(); break;
                    default: throw new IllegalArgumentException("未知内容操作");
                }
                call.resolve(new JSObject(result.toString()));
            } catch (Exception error) {
                call.reject(error instanceof ContentVerifier.Failure ? error.getMessage() : "内容操作未完成，已有剧本已保留");
            }
        });
    }
    @PluginMethod public void libraryImport(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        // OEM providers may not assign a MIME type to .mmstory. Trust is
        // checked from the signed bytes after selection, never the extension.
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivityForResult(call, intent, "contentSelected");
    }
    @ActivityCallback private void contentSelected(PluginCall call, ActivityResult result) {
        if (call == null) return;
        if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null || result.getData().getData() == null) {
            call.resolve(new JSObject().put("cancelled", true)); return;
        }
        var uri = result.getData().getData();
        libraryControl.execute(() -> {
            try {
                if (!"content".equals(uri.getScheme())) throw new IllegalArgumentException();
                var stream = getContext().getContentResolver().openInputStream(uri);
                if (stream == null) throw new IllegalArgumentException();
                try { call.resolve(new JSObject(StoryLibraryHost.get(getContext()).installFile(stream).toString())); }
                catch (Exception error) { stream.close(); throw error; }
            } catch (Exception error) { call.reject("无法读取内容包，请选择官方 .mmstory 文件"); }
        });
    }

    @PluginMethod public void command(PluginCall call) {
        JSObject command = call.getObject("command");
        if (command == null) { call.reject("缺少引擎命令"); return; }
        bridgeWorker.execute(() -> {
            try { call.resolve(new JSObject(host.command(command.toString()))); }
            catch (Exception error) {
                if (BuildConfig.DEBUG) android.util.Log.e("MysteryEngine", "Engine initialization failed", error);
                call.reject("本地引擎初始化失败，请重新启动应用");
            }
        });
    }

    @PluginMethod public void draft(PluginCall call) {
        String gameId = call.getString("gameId", "");
        if (!gameId.matches("[a-zA-Z0-9-]{1,64}")) { call.reject("无效的游戏标识"); return; }
        bridgeWorker.execute(() -> {
            android.content.SharedPreferences prefs = getContext().getSharedPreferences("drafts-v1", 0);
            String value = call.getString("value");
            if (value != null && (value.length() > 1000 || !prefs.edit().putString(gameId, value).commit())) {
                call.reject("草稿保存失败"); return;
            }
            call.resolve(new JSObject().put("value", prefs.getString(gameId, "")));
        });
    }

    @PluginMethod public void settings(PluginCall call) {
        bridgeWorker.execute(() -> {
            try { call.resolve(new JSObject(host.vault.settings().toString())); }
            catch (Exception error) { call.reject("无法读取模型配置"); }
        });
    }

    @PluginMethod public void openSettings(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            try {
                JSONObject config = host.vault.settings();
                LinearLayout form = new LinearLayout(getActivity());
                form.setOrientation(LinearLayout.VERTICAL);
                int pad = (int)(20 * getContext().getResources().getDisplayMetrics().density);
                form.setPadding(pad, pad, pad, pad);
                EditText base = field(form, "API 地址", config.getString("baseUrl"), false);
                EditText key = field(form, config.getBoolean("configured") ? "API key（已保存，留空保持）" : "API key", "", true);
                EditText story = field(form, "剧本模型", config.getString("storyModel"), false);
                EditText role = field(form, "角色模型", config.getString("roleModel"), false);
                EditText review = field(form, "审稿模型", config.getString("reviewModel"), false);
                CheckBox thinking = new CheckBox(getActivity());
                thinking.setText("支持 DeepSeek thinking 参数（其他服务可关闭）");
                thinking.setChecked(config.getBoolean("thinking")); form.addView(thinking);
                TextView note = new TextView(getActivity());
                note.setText("密钥仅在手机加密保存。三个模型可共用同一份密钥；画像未配置时使用文字头像。");
                form.addView(note);
                ScrollView scroll = new ScrollView(getActivity()); scroll.addView(form);
                AlertDialog dialog = new AlertDialog.Builder(getActivity()).setTitle("模型设置")
                    .setView(scroll).setPositiveButton("保存", null).setNegativeButton("取消", (d, w) -> call.resolve()).create();
                dialog.setOnCancelListener(d -> call.resolve());
                dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                    String secret = key.getText().toString();
                    String url = base.getText().toString(), s = story.getText().toString();
                    String r = role.getText().toString(), check = review.getText().toString();
                    boolean supportsThinking = thinking.isChecked();
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                    bridgeWorker.execute(() -> {
                        try {
                            host.vault.save(url, s, r, check, secret, supportsThinking);
                            getActivity().runOnUiThread(() -> { key.setText(""); dialog.dismiss(); call.resolve(); });
                        } catch (Exception error) {
                            getActivity().runOnUiThread(() -> {
                                dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
                                Toast.makeText(getContext(), error instanceof IllegalArgumentException ? error.getMessage() : "密钥保存失败，请重试", Toast.LENGTH_LONG).show();
                            });
                        }
                    });
                }));
                dialog.show();
                dialog.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
            } catch (Exception error) { call.reject("无法打开模型设置"); }
        });
    }

    private EditText field(LinearLayout form, String label, String value, boolean secret) {
        TextView title = new TextView(getActivity()); title.setText(label); form.addView(title);
        EditText input = new EditText(getActivity()); input.setSingleLine(true); input.setText(value);
        input.setInputType(InputType.TYPE_CLASS_TEXT | (secret ? InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS));
        if (android.os.Build.VERSION.SDK_INT >= 26) input.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);
        form.addView(input); return input;
    }
}
