package com.murdermystery.game;

import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeWebViewClient;
import java.io.File;
import java.io.FileInputStream;
import java.util.Collections;
import java.util.regex.Pattern;

/** Serve immutable downloaded artwork; all other routes keep Capacitor behavior. */
final class StoryAssetHandler extends BridgeWebViewClient {
    private final File packs;
    private static final Pattern ROUTE = Pattern.compile("^/assets/story-library/packs/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/([1-9][0-9]{0,9})/([a-f0-9]{64})/([A-Za-z0-9_-]+\\.webp)$");
    StoryAssetHandler(Bridge bridge, File files) { super(bridge); packs = new File(files, "story-library/packs"); }
    @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
        var uri = request.getUrl();
        if (!"https".equals(uri.getScheme()) || !"localhost".equals(uri.getHost()) || (uri.getPort() != -1 && uri.getPort() != 443)
            || !uri.getPath().startsWith("/assets/story-library/packs/")) return super.shouldInterceptRequest(view, request);
        try {
            var match = ROUTE.matcher(uri.getPath());
            if (!request.getMethod().equals("GET") || !match.matches()) return missing();
            File directory = new File(packs, match.group(1) + "/v" + match.group(2) + "-" + match.group(3));
            File image = new File(directory, "images/" + match.group(4));
            if (!new File(directory, "complete.json").isFile() || !image.isFile() || image.length() > 4 * 1024 * 1024
                || !image.getCanonicalPath().startsWith(packs.getCanonicalPath() + File.separator)) return missing();
            var marker = ContentJson.parse(new String(ContentVerifier.readLimited(new FileInputStream(new File(directory, "complete.json")), 4096), java.nio.charset.StandardCharsets.UTF_8));
            if (!marker.getString("story_id").equals(match.group(1)) || !String.valueOf(marker.getInt("version")).equals(match.group(2))
                || !marker.getString("sha256").equals(match.group(3))) return missing();
            return new WebResourceResponse("image/webp", null, 200, "OK",
                Collections.singletonMap("Cache-Control", "private, max-age=31536000, immutable"), new FileInputStream(image));
        } catch (Exception ignored) { return missing(); }
    }
    private WebResourceResponse missing() {
        return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", Collections.emptyMap(), new java.io.ByteArrayInputStream(new byte[0]));
    }
}
