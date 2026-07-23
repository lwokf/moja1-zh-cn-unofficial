package io.github.moja1zh;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.pm.PackageInfo;
import android.content.res.Resources;
import android.text.Spanned;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

public final class MojA1ZhHook implements IXposedHookLoadPackage {
    private static final String LOG_PREFIX = "[MojA1Zh] ";

    private static final Map<String, Map<String, Rule>> RESOURCE_BY_LANGUAGE =
            new HashMap<String, Map<String, Rule>>();
    private static final Map<String, Map<String, Rule>> LOCAL_BY_LANGUAGE =
            new HashMap<String, Map<String, Rule>>();
    private static final Map<String, Map<String, List<ServerRule>>> SERVER_BY_LANGUAGE =
            new HashMap<String, Map<String, List<ServerRule>>>();
    private static final Map<String, List<ServerPatternRule>> PATTERNS_BY_LANGUAGE =
            new HashMap<String, List<ServerPatternRule>>();
    private static final Set<String> LOGGED_RULES =
            Collections.synchronizedSet(new HashSet<String>());

    private static volatile boolean active;
    private static volatile String activeLanguage;
    private static boolean frameworkHooksInstalled;
    private static boolean optionalHooksInstalled;

    static {
        for (String[] row : TranslationData.RESOURCE_RULES) {
            Map<String, Rule> rules = RESOURCE_BY_LANGUAGE.get(row[0]);
            if (rules == null) {
                rules = new HashMap<String, Rule>();
                RESOURCE_BY_LANGUAGE.put(row[0], rules);
            }
            rules.put(row[2], new Rule(row[1], row[3]));
        }
        for (String[] row : TranslationData.LOCAL_EXACT_RULES) {
            Map<String, Rule> rules = LOCAL_BY_LANGUAGE.get(row[0]);
            if (rules == null) {
                rules = new HashMap<String, Rule>();
                LOCAL_BY_LANGUAGE.put(row[0], rules);
            }
            rules.put(row[2], new Rule(row[1], row[3]));
        }
        for (String[] row : TranslationData.SERVER_EXACT_RULES) {
            Map<String, List<ServerRule>> bySource = SERVER_BY_LANGUAGE.get(row[0]);
            if (bySource == null) {
                bySource = new HashMap<String, List<ServerRule>>();
                SERVER_BY_LANGUAGE.put(row[0], bySource);
            }
            List<ServerRule> rules = bySource.get(row[2]);
            if (rules == null) {
                rules = new ArrayList<ServerRule>();
                bySource.put(row[2], rules);
            }
            rules.add(new ServerRule(row[1], row[3], row[4], row[5]));
        }
        for (String[] row : TranslationData.SERVER_PATTERN_RULES) {
            List<ServerPatternRule> rules = PATTERNS_BY_LANGUAGE.get(row[0]);
            if (rules == null) {
                rules = new ArrayList<ServerPatternRule>();
                PATTERNS_BY_LANGUAGE.put(row[0], rules);
            }
            rules.add(new ServerPatternRule(
                    row[1], Pattern.compile(row[2]), row[3], row[4], row[5]));
        }
    }

    public void handleLoadPackage(final XC_LoadPackage.LoadPackageParam lpparam) throws Throwable {
        if (!TranslationData.TARGET_PACKAGE.equals(lpparam.packageName)
                || !TranslationData.TARGET_PROCESS.equals(lpparam.processName)) {
            return;
        }

        synchronized (MojA1ZhHook.class) {
            if (frameworkHooksInstalled) {
                return;
            }
            frameworkHooksInstalled = true;
        }

        installResourceHooks();
        installViewHooks();

        XposedBridge.hookAllMethods(Application.class, "attach", new XC_MethodHook() {
            protected void afterHookedMethod(MethodHookParam param) {
                if (param.args == null || param.args.length == 0 || !(param.args[0] instanceof Context)) {
                    log("gate=disabled reason=no_context");
                    return;
                }
                Context context = (Context) param.args[0];
                evaluateGate(context);
                if (active) {
                    installOptionalMaterialHooks(lpparam.classLoader);
                }
            }
        });
    }

    private static void installResourceHooks() {
        XposedBridge.hookAllMethods(Resources.class, "getText", new XC_MethodHook() {
            protected void afterHookedMethod(MethodHookParam param) {
                replaceResourceResult(param, false);
            }
        });
        XposedBridge.hookAllMethods(Resources.class, "getString", new XC_MethodHook() {
            protected void afterHookedMethod(MethodHookParam param) {
                replaceResourceResult(param, true);
            }
        });
    }

    private static void installViewHooks() {
        XposedBridge.hookAllMethods(TextView.class, "setText", new TextSetterHook(true, true));
        XposedBridge.hookAllMethods(TextView.class, "setHint", new TextSetterHook(false, false));
        XposedBridge.hookAllMethods(TextView.class, "setError", new TextSetterHook(false, false));
        XposedBridge.hookAllMethods(View.class, "setContentDescription", new TextSetterHook(true, false));
    }

    private static void installOptionalMaterialHooks(ClassLoader classLoader) {
        synchronized (MojA1ZhHook.class) {
            if (optionalHooksInstalled) {
                return;
            }
            optionalHooksInstalled = true;
        }
        try {
            Class<?> textInputLayout = Class.forName(
                    "com.google.android.material.textfield.TextInputLayout", false, classLoader);
            XposedBridge.hookAllMethods(textInputLayout, "setHint", new TextSetterHook(false, false));
            XposedBridge.hookAllMethods(textInputLayout, "setError", new TextSetterHook(false, false));
            XposedBridge.hookAllMethods(textInputLayout, "setHelperText", new TextSetterHook(false, false));
            XposedBridge.hookAllMethods(textInputLayout, "setPlaceholderText", new TextSetterHook(false, false));
            log("optional_material_hooks=installed");
        } catch (Throwable error) {
            logFailure("optional_material_hooks", error);
        }
    }

    private static void evaluateGate(Context context) {
        active = false;
        activeLanguage = null;
        try {
            if (!TranslationData.TARGET_PACKAGE.equals(context.getPackageName())) {
                log("gate=disabled reason=package");
                return;
            }
            PackageInfo info = context.getPackageManager().getPackageInfo(TranslationData.TARGET_PACKAGE, 0);
            if (info.versionCode != TranslationData.TARGET_VERSION_CODE) {
                log("gate=disabled reason=version actual=" + info.versionCode);
                return;
            }
            Locale locale = context.getResources().getConfiguration().locale;
            if (locale == null) {
                locale = Locale.getDefault();
            }
            String language = resolveLanguage(locale);
            if (language == null) {
                log("gate=disabled reason=locale");
                return;
            }
            activeLanguage = language;
            active = true;
            log("gate=enabled version=" + info.versionCode + " catalogue="
                    + TranslationData.CATALOGUE_SHA256.substring(0, 12)
                    + " language=" + language);
        } catch (Throwable error) {
            active = false;
            activeLanguage = null;
            logFailure("gate", error);
        }
    }

    private static String resolveLanguage(Locale locale) {
        if (locale == null) {
            return null;
        }
        String tag = locale.toLanguageTag();
        if (tag == null || tag.length() == 0) {
            return null;
        }
        tag = tag.replace('_', '-').toLowerCase(Locale.US);
        for (String[] row : TranslationData.LANGUAGE_MATCH_RULES) {
            if (row[1].equals(tag)) {
                return row[0];
            }
        }
        return null;
    }

    private static void replaceResourceResult(XC_MethodHook.MethodHookParam param, boolean format) {
        if (!active || param.hasThrowable() || !(param.thisObject instanceof Resources)
                || param.args == null || param.args.length == 0 || !(param.args[0] instanceof Integer)) {
            return;
        }
        try {
            Resources resources = (Resources) param.thisObject;
            int id = ((Integer) param.args[0]).intValue();
            String language = activeLanguage;
            if (language == null) {
                return;
            }
            Rule rule = findResourceRule(resources, id, language);
            if (rule == null) {
                return;
            }
            String translated = rule.target;
            if (format && param.args.length > 1 && param.args[1] instanceof Object[]) {
                try {
                    translated = String.format(
                            Locale.forLanguageTag(language), translated, (Object[]) param.args[1]);
                } catch (Throwable error) {
                    logFailure("format." + rule.id, error);
                    return;
                }
            }
            param.setResult(translated);
            logHit(rule.id);
        } catch (Throwable error) {
            logFailure("resource", error);
        }
    }

    private static Rule findResourceRule(Resources resources, int id, String language) {
        try {
            if (!TranslationData.TARGET_PACKAGE.equals(resources.getResourcePackageName(id))) {
                return null;
            }
            Map<String, Rule> rules = RESOURCE_BY_LANGUAGE.get(language);
            if (rules == null) {
                return null;
            }
            return rules.get(resources.getResourceEntryName(id));
        } catch (Resources.NotFoundException ignored) {
            return null;
        }
    }

    private static String translateLocal(CharSequence value) {
        if (value == null || value instanceof Spanned) {
            return null;
        }
        String language = activeLanguage;
        if (language == null) {
            return null;
        }
        Map<String, Rule> rules = LOCAL_BY_LANGUAGE.get(language);
        if (rules == null) {
            return null;
        }
        Rule rule = rules.get(value.toString());
        if (rule == null) {
            return null;
        }
        logHit(rule.id);
        return rule.target;
    }

    private static String translateServer(View view, CharSequence value) {
        // Server rules also require exact Activity and view-id matches, so a
        // styled CharSequence can safely be replaced after exact toString()
        // comparison. Local rich text remains fail-open in translateLocal().
        if (view == null || value == null) {
            return null;
        }
        String language = activeLanguage;
        if (language == null) {
            return null;
        }
        String source = value.toString();
        Map<String, List<ServerRule>> bySource = SERVER_BY_LANGUAGE.get(language);
        List<ServerRule> candidates = bySource == null ? null : bySource.get(source);
        List<ServerPatternRule> patternRules = PATTERNS_BY_LANGUAGE.get(language);
        if ((candidates == null || candidates.isEmpty())
                && (patternRules == null || patternRules.isEmpty())) {
            return null;
        }
        Activity activity = findActivity(view.getContext());
        if (activity == null) {
            return null;
        }
        String activityName = activity.getClass().getName();
        String viewName = getTargetViewName(view);
        if (viewName == null) {
            return null;
        }
        if (candidates != null) {
            for (ServerRule rule : candidates) {
                if (rule.activity.equals(activityName) && rule.viewName.equals(viewName)) {
                    logHit(rule.id);
                    return rule.target;
                }
            }
        }
        if (patternRules != null) {
            for (ServerPatternRule rule : patternRules) {
                if (!rule.activity.equals(activityName) || !rule.viewName.equals(viewName)) {
                    continue;
                }
                Matcher matcher = rule.pattern.matcher(source);
                if (matcher.matches()) {
                    try {
                        String translated = matcher.replaceFirst(rule.replacement);
                        logHit(rule.id);
                        return translated;
                    } catch (Throwable error) {
                        logFailure("pattern." + rule.id, error);
                        return null;
                    }
                }
            }
        }
        return null;
    }

    private static Activity findActivity(Context context) {
        Context current = context;
        for (int depth = 0; current != null && depth < 12; depth++) {
            if (current instanceof Activity) {
                return (Activity) current;
            }
            if (!(current instanceof ContextWrapper)) {
                return null;
            }
            Context next = ((ContextWrapper) current).getBaseContext();
            if (next == current) {
                return null;
            }
            current = next;
        }
        return null;
    }

    private static String getTargetViewName(View view) {
        int id = view.getId();
        if (id == View.NO_ID) {
            return null;
        }
        try {
            Resources resources = view.getResources();
            if (!TranslationData.TARGET_PACKAGE.equals(resources.getResourcePackageName(id))) {
                return null;
            }
            return resources.getResourceEntryName(id);
        } catch (Resources.NotFoundException ignored) {
            return null;
        }
    }

    private static void logHit(String ruleId) {
        if (LOGGED_RULES.add(ruleId)) {
            log("hit=" + ruleId);
        }
    }

    private static void logFailure(String stage, Throwable error) {
        String type = error == null ? "unknown" : error.getClass().getName();
        log("fail_open stage=" + stage + " type=" + type);
    }

    private static void log(String value) {
        XposedBridge.log(LOG_PREFIX + value);
    }

    private static final class TextSetterHook extends XC_MethodHook {
        private final boolean allowServer;
        private final boolean skipEditText;

        TextSetterHook(boolean allowServer, boolean skipEditText) {
            this.allowServer = allowServer;
            this.skipEditText = skipEditText;
        }

        protected void beforeHookedMethod(MethodHookParam param) {
            if (!active || param.args == null || param.args.length == 0
                    || !(param.args[0] instanceof CharSequence)) {
                return;
            }
            if (skipEditText && param.thisObject instanceof EditText) {
                return;
            }
            try {
                CharSequence source = (CharSequence) param.args[0];
                String translated = null;
                if (allowServer && param.thisObject instanceof View) {
                    translated = translateServer((View) param.thisObject, source);
                }
                if (translated == null) {
                    translated = translateLocal(source);
                }
                if (translated != null) {
                    param.args[0] = translated;
                }
            } catch (Throwable error) {
                logFailure("setter", error);
            }
        }
    }

    private static class Rule {
        final String id;
        final String target;

        Rule(String id, String target) {
            this.id = id;
            this.target = target;
        }
    }

    private static final class ServerRule extends Rule {
        final String activity;
        final String viewName;

        ServerRule(String id, String target, String activity, String viewName) {
            super(id, target);
            this.activity = activity;
            this.viewName = viewName;
        }
    }

    private static final class ServerPatternRule {
        final String id;
        final Pattern pattern;
        final String replacement;
        final String activity;
        final String viewName;

        ServerPatternRule(
                String id,
                Pattern pattern,
                String replacement,
                String activity,
                String viewName) {
            this.id = id;
            this.pattern = pattern;
            this.replacement = replacement;
            this.activity = activity;
            this.viewName = viewName;
        }
    }
}
