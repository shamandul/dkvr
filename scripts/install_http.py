#!/usr/bin/env python3
"""Cliente HTTP basico para Drupal (login, formularios, batch).

Se puede usar como script (instala el sitio) o importar como modulo:
  import install_http as U ; U.req(...) ; U.parse_form(...)

BASE: DRUPAL_BASE o argv[1]. Cabecera Host: DRUPAL_HOST_HEADER (util desde
dentro de la red de compose, p. ej. DRUPAL_HOST_HEADER=drupal).
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

BASE = os.environ.get("DRUPAL_BASE", "http://127.0.0.1:8080")
if len(sys.argv) > 1:
    BASE = sys.argv[1].rstrip("/")
PROFILE = "standard"
LOCALE = "en"
SITE_NAME = "Kafka Drupal"
SITE_MAIL = "admin@example.com"
ADMIN_NAME = "admin"
ADMIN_PASS = "Kafka123!"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj), NoRedirect
)


def log(*args):
    print(*args, flush=True)


def req(url, data=None, timeout=180):
    r = urllib.request.Request(url, data=data)
    r.add_header("User-Agent", "Mozilla/5.0 install-driver")
    if os.environ.get("DRUPAL_HOST_HEADER"):
        r.add_header("Host", os.environ["DRUPAL_HOST_HEADER"])
    if data is not None:
        r.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        resp = opener.open(r, timeout=timeout)
        return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def parse_form(text):
    for m in re.finditer(r"<form\b([^>]*)>(.*?)</form>", text, re.S | re.I):
        attrs, content = m.group(1), m.group(2)
        if not re.search(r'name="op"', content, re.I):
            continue
        am = re.search(r'action="([^"]*)"', attrs, re.I)
        action = html.unescape(am.group(1)) if am else ""
        fid = re.search(r'name="form_id"\s+value="([^"]*)"', content, re.I)
        fields = {}
        for im in re.finditer(r"<input\b([^>]*)>", content, re.I):
            ia = im.group(1)
            nm = re.search(r'name="([^"]*)"', ia)
            if not nm:
                continue
            tp = re.search(r'type="([^"]*)"', ia)
            typ = tp.group(1).lower() if tp else "text"
            if typ in ("checkbox", "radio") and "checked" not in ia.lower():
                continue
            vm = re.search(r'value="([^"]*)"', ia)
            fields[nm.group(1)] = html.unescape(vm.group(1)) if vm else ""
        for sm in re.finditer(r"<select\b([^>]*)>(.*?)</select>", content, re.S | re.I):
            nm = re.search(r'name="([^"]*)"', sm.group(1))
            if not nm:
                continue
            chosen = None
            for o in re.finditer(r"<option\b([^>]*)>", sm.group(2), re.I):
                ov = re.search(r'value="([^"]*)"', o.group(1))
                val = html.unescape(ov.group(1)) if ov else ""
                if chosen is None:
                    chosen = val
                if "selected" in o.group(1).lower():
                    chosen = val
                    break
            fields[nm.group(1)] = chosen or ""
        for tm in re.finditer(r"<textarea\b([^>]*)>(.*?)</textarea>", content, re.S | re.I):
            nm = re.search(r'name="([^"]*)"', tm.group(1))
            if nm:
                fields[nm.group(1)] = html.unescape(tm.group(2))
        return action, fid.group(1) if fid else "", fields
    return None, "", None


def fill_configure(fields):
    out = {}
    for k, v in fields.items():
        kl = k.lower()
        if k == "site_name":
            out[k] = SITE_NAME
        elif k == "site_mail":
            out[k] = SITE_MAIL
        elif k == "account[name]":
            out[k] = ADMIN_NAME
        elif k == "account[mail]":
            out[k] = SITE_MAIL
        elif "pass" in kl:
            out[k] = ADMIN_PASS
        else:
            out[k] = v
    return out


def main():
    method = "GET"
    url = f"{BASE}/core/install.php?profile={PROFILE}&locale={LOCALE}"
    payload = None
    for step in range(1, 80):
        code, body, headers = req(url, payload if method == "POST" else None)
        log(f"[{step}] {method} {url[:150]} -> {code} ({len(body)}B)")
        method, payload = "GET", None

        if code in (301, 302, 303, 307, 308):
            loc = headers.get("Location")
            url = urllib.parse.urljoin(url, html.unescape(loc))
            continue
        if code >= 400:
            log("!! HTTP", code)
            log(body.decode("utf-8", "replace")[:3000])
            return 1

        text = body.decode("utf-8", "replace")

        if text.lstrip().startswith("{"):
            try:
                j = json.loads(text)
            except Exception:
                j = None
            if isinstance(j, dict) and j.get("url"):
                url = urllib.parse.urljoin(url, j["url"])
                continue
            if isinstance(j, dict) and j.get("op") == "finished":
                log("   batch finished:", j)
                continue
            log("!! JSON inesperado:", text[:500])
            return 1

        # Formulario?
        action, form_id, fields = parse_form(text)
        if fields is not None:
            post_url = urllib.parse.urljoin(url, action)
            if form_id == "install_configure_form":
                fields = fill_configure(fields)
                log(f"   enviando configure_form ({len(fields)} campos)")
            else:
                log(f"   enviando {form_id or 'form'} ({len(fields)} campos)")
            method, url, payload = "POST", post_url, urllib.parse.urlencode(fields).encode()
            continue

        # Las paginas de progreso de Batch llevan drupalSettings.batch
        is_batch_page = bool(re.search(r'"batch"\s*:\s*\{', text))

        if not is_batch_page and re.search(
            r"UnmetDependenciesException|Uncaught (?:Exception|Error)|Fatal error"
            r"|The installation has encountered an error|Drupal\\Core\\.*Exception",
            text,
            re.I,
        ):
            log("!! PAGINA DE ERROR")
            body_txt = re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)
            body_txt = re.sub(r"<style.*?</style>", "", body_txt, flags=re.S | re.I)
            body_txt = re.sub(r"<[^>]+>", " ", body_txt)
            log(re.sub(r"\s+", " ", body_txt)[:3000])
            return 1

        # Pagina final (sin formulario ni batch en curso)
        if not is_batch_page and re.search(r"<title>", text, re.I):
            t = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
            log("=== INSTALACION COMPLETADA ("
                + re.sub(r"\s+", " ", t.group(1)).strip() + ") ===")
            break

        m = re.search(r'href="([^"]*op=do_nojs[^"]*)"', text, re.I)
        if m:
            url = urllib.parse.urljoin(url, html.unescape(m.group(1)))
            continue

        # Meta refresh (modo no-JS de Batch API)
        m = re.search(r'http-equiv="Refresh"\s+content="[^"]*URL=([^"]+)"', text, re.I)
        if not m:
            m = re.search(r'content="[^"]*URL=([^"]+)"\s+http-equiv="Refresh"', text, re.I)
        if m:
            url = urllib.parse.urljoin(url, html.unescape(m.group(1)))
            continue

        # drupalSettings.batch.uri (fallback)
        m = re.search(r'"batch"\s*:\s*\{.*?"uri"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.S)
        if m:
            url = urllib.parse.urljoin(url, json.loads('"' + m.group(1) + '"'))
            continue

        log("!! HTML no reconocido:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))[:600])
        return 1
    else:
        log("!! se supero el limite de pasos")
        return 1

    for path in ("/", "/user/login"):
        cur, hops = f"{BASE}{path}", 0
        while hops < 6:
            code, body, headers = req(cur)
            if code in (301, 302, 303, 307, 308):
                cur = urllib.parse.urljoin(cur, html.unescape(headers.get("Location")))
                hops += 1
                continue
            t = re.search(r"<title>(.*?)</title>", body.decode("utf-8", "replace"), re.S)
            log(f"GET {path} -> {code} | "
                + (re.sub(r"\s+", " ", t.group(1)).strip() if t else ""))
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
