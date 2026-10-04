#!/usr/bin/env python3
"""Habilita un modulo de Drupal via HTTP (login + /admin/modules).

Uso:
  DRUPAL_HOST_HEADER=<host> python3 scripts/enable_module.py <BASE_URL> <modulo>

Ejemplos (los dos entornos):
  DRUPAL_HOST_HEADER=drupal      python3 scripts/enable_module.py http://drupal environment_info
  DRUPAL_HOST_HEADER=drupal.local python3 scripts/enable_module.py http://drupal.local environment_info
"""
import html
import json
import re
import sys
import urllib.parse

import install_http as U

MODULE = sys.argv[2] if len(sys.argv) > 2 else "environment_info"
ADMIN = "admin"
PASS = "Kafka123!"


def decode(body):
    return body.decode("utf-8", "replace")


def redirect(hdr, base):
    loc = hdr.get("Location")
    return urllib.parse.urljoin(base, html.unescape(loc))


def drain(start_url, max_hops=25):
    """Sigue 3xx, meta-refresh de batch y drupalSettings.batch.uri."""
    url = start_url
    for _ in range(max_hops):
        code, body, hdr = U.req(url)
        U.log(f"   GET {url[:120]} -> {code} ({len(body)}B)")
        if code in (301, 302, 303, 307, 308):
            url = redirect(hdr, url)
            continue
        text = decode(body)
        if text.lstrip().startswith("{"):
            try:
                j = json.loads(text)
            except Exception:
                j = None
            if isinstance(j, dict) and j.get("url"):
                url = urllib.parse.urljoin(url, j["url"])
                continue
        m = re.search(r'http-equiv="Refresh"\s+content="[^"]*URL=([^"]+)"', text, re.I)
        if m:
            url = urllib.parse.urljoin(url, html.unescape(m.group(1)))
            continue
        m = re.search(r'"batch"\s*:\s*\{.*?"uri"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.S)
        if m:
            url = urllib.parse.urljoin(url, json.loads('"' + m.group(1) + '"'))
            continue
        return code, text, url
    return None, "", url


def main():
    U.log(f"BASE={U.BASE} modulo={MODULE}")

    # 1) login
    login_url = f"{U.BASE}/user/login"
    code, body, hdr = U.req(login_url)
    action, _fid, fields = U.parse_form(decode(body))
    if fields is None:
        U.log("!! no se encontro el formulario de login")
        return 1
    fields["name"] = ADMIN
    fields["pass"] = PASS
    post_url = urllib.parse.urljoin(login_url, action or "")
    code, body, hdr = U.req(post_url, urllib.parse.urlencode(fields).encode())
    U.log(f"login -> {code}")
    if code in (301, 302, 303, 307, 308):
        code, text, final = drain(redirect(hdr, post_url))
    else:
        text, final = decode(body), post_url
    if "admin/content" not in final and "/user/login" in final:
        U.log("!! login fallido")
        return 1

    # 2) /admin/modules
    mods_url = f"{U.BASE}/admin/modules"
    code, body, hdr = U.req(mods_url)
    text = decode(body)
    U.log(f"/admin/modules -> {code}")
    action, fid, fields = U.parse_form(text)
    if fields is None:
        U.log("!! no se encontro el formulario de modulos")
        return 1
    U.log(f"   form_id={fid!r} campos={len(fields)}")
    # Drupal 11 usa modules[<nombre>][enable] (Drupal 10: modules[<nombre>]).
    m = re.search(
        rf'name="modules\[{re.escape(MODULE)}\]\[enable\]"', text
    ) or re.search(rf'name="modules\[{re.escape(MODULE)}\]"', text)
    if not m:
        U.log(f"!! no aparece el checkbox del modulo {MODULE} en el formulario")
        return 1
    fields[m.group(0)[6:-1]] = "1"
    post_url = urllib.parse.urljoin(mods_url, action or "")
    code, body, hdr = U.req(post_url, urllib.parse.urlencode(fields).encode())
    U.log(f"POST modulo -> {code}")
    code, text, final = drain(
        redirect(hdr, post_url) if code in (301, 302, 303, 307, 308) else post_url
    )

    # 3) comprobacion: mensaje de exito o checkbox en estado disabled
    #    (Drupal renderiza los modulos ya habilitados con disabled="disabled")
    ok_msg = re.search(
        r"has been enabled|habilitado|successfully", text or "", re.I
    )
    tag = re.search(
        rf"<input[^>]*name=\"modules\[{re.escape(MODULE)}\]\[enable\]\"[^>]*>",
        text or "",
    ) or re.search(
        rf"<input[^>]*name=\"modules\[{re.escape(MODULE)}\]\"[^>]*>", text or ""
    )
    checked = bool(tag and ("disabled" in tag.group(0) or "checked" in tag.group(0)))
    if ok_msg or checked:
        U.log("=== MODULO HABILITADO ===")
        return 0
    U.log("!! no se pudo confirmar la habilitacion")
    U.log(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))[:800])
    return 1


if __name__ == "__main__":
    sys.exit(main())
