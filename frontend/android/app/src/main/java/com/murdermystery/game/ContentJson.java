package com.murdermystery.game;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;

/** Strict bounded JSON: Android's JSONObject otherwise silently replaces keys. */
final class ContentJson {
    private final String text;
    private int position, nodes;
    private ContentJson(String text) { this.text = text; }
    static JSONObject parse(String text) throws Exception {
        ContentJson parser = new ContentJson(text);
        Object result = parser.value(0);
        parser.space();
        if (!(result instanceof JSONObject) || parser.position != text.length()) throw new IllegalArgumentException("内容 JSON 无效");
        return (JSONObject) result;
    }
    private void space() {
        while (position < text.length() && " \t\r\n".indexOf(text.charAt(position)) >= 0) position++;
    }
    private boolean take(char value) {
        space();
        if (position < text.length() && text.charAt(position) == value) { position++; return true; }
        return false;
    }
    private void need(char value) {
        if (!take(value)) throw new IllegalArgumentException("内容 JSON 无效");
    }
    private String string() throws Exception {
        space();
        int start = position;
        need('"');
        boolean escaped = false;
        while (position < text.length()) {
            char current = text.charAt(position++);
            if (current < 32) throw new IllegalArgumentException("JSON 字符串无效");
            if (!escaped && current == '"') {
                String raw = text.substring(start, position);
                // Android's tokener accepts unknown escapes; restrict them here.
                for (int i = 1; i < raw.length() - 1; i++) {
                    if (raw.charAt(i) != '\\') continue;
                    char next = raw.charAt(++i);
                    if ("\"\\/bfnrtu".indexOf(next) < 0) throw new IllegalArgumentException("JSON 转义无效");
                    if (next == 'u') {
                        if (i + 4 >= raw.length() || !raw.substring(i + 1, i + 5).matches("[a-fA-F0-9]{4}")) throw new IllegalArgumentException("JSON 转义无效");
                        i += 4;
                    }
                }
                return (String) new JSONTokener(raw).nextValue();
            }
            if (!escaped && current == '\\') escaped = true;
            else escaped = false;
        }
        throw new IllegalArgumentException("JSON 字符串未结束");
    }
    private Object value(int depth) throws Exception {
        if (depth > 32 || ++nodes > 100000) throw new IllegalArgumentException("JSON 超过结构限制");
        space();
        if (position >= text.length()) throw new IllegalArgumentException("JSON 不完整");
        char next = text.charAt(position);
        if (next == '"') return string();
        if (take('{')) {
            JSONObject object = new JSONObject();
            if (take('}')) return object;
            do {
                String key = string();
                if (object.has(key)) throw new IllegalArgumentException("JSON 字段重复");
                need(':'); object.put(key, value(depth + 1));
            } while (take(','));
            need('}'); return object;
        }
        if (take('[')) {
            JSONArray array = new JSONArray();
            if (take(']')) return array;
            do { array.put(value(depth + 1)); } while (take(','));
            need(']'); return array;
        }
        int start = position;
        while (position < text.length() && " \t\r\n,]}".indexOf(text.charAt(position)) < 0) position++;
        String token = text.substring(start, position);
        if (token.equals("true")) return true;
        if (token.equals("false")) return false;
        if (token.equals("null")) return JSONObject.NULL;
        if (!token.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?")) throw new IllegalArgumentException("JSON 数值无效");
        if (!token.contains(".") && !token.contains("e") && !token.contains("E")) return Long.parseLong(token);
        double number = Double.parseDouble(token);
        if (!Double.isFinite(number)) throw new IllegalArgumentException("JSON 数值无效");
        return number;
    }
}
