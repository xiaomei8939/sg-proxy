#!/usr/bin/env python3
"""Google signup attempt v2 — new lifecycle flow uses custom dropdowns.

Dumps visible interactive elements into status.json before each step so
failures are diagnosable. Reads PW from env. Stops at whatever gate appears
after the password step without inventing any data.
"""
import json, os, sys
from playwright.sync_api import sync_playwright

SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shots')
os.makedirs(SHOTS, exist_ok=True)
PW = os.environ.get('PW', '')
USERNAME = os.environ.get('USERNAME', 'yya249666793')
log = []


def dump_dom(page):
    try:
        return page.evaluate("""() => {
          const els = [...document.querySelectorAll('input, select, [role=listbox], [role=radio], [aria-haspopup=listbox], button')];
          return els.slice(0, 60).map(e => ({
            tag: e.tagName, type: e.getAttribute('type'), id: e.id,
            name: e.getAttribute('name'), role: e.getAttribute('role'),
            label: e.getAttribute('aria-label'),
            visible: !!(e.offsetWidth || e.offsetHeight)
          }));
        }""")
    except Exception as e:
        return f'dump failed: {e}'


def note(step, page, extra=''):
    fn = f'{len(log):02d}-{step}.png'
    try:
        page.screenshot(path=os.path.join(SHOTS, fn))
    except Exception as e:
        fn = f'screenshot-failed: {e}'
    text = ''
    try:
        text = page.locator('body').inner_text(timeout=3000)[:1200]
    except Exception:
        pass
    log.append({'step': step, 'shot': fn, 'url': page.url, 'extra': extra,
                'text': text, 'dom': dump_dom(page)})
    with open(os.path.join(SHOTS, 'status.json'), 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(f'[{step}] {page.url} {extra}', flush=True)


def click_next(page):
    for sel in ['button:has-text("Next")', 'button:has-text("下一步")']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                return True
        except Exception:
            continue
    return False


def pick_dropdown(page, opener_labels, option_text):
    """Open a custom dropdown by label, then click the option text."""
    for lab in opener_labels:
        try:
            op = page.get_by_label(lab, exact=False).first
            if op.is_visible(timeout=1200):
                op.click()
                page.wait_for_timeout(700)
                opt = page.get_by_role('option', name=option_text).first
                if opt.is_visible(timeout=1500):
                    opt.click()
                    return True
                opt = page.locator(f'[role="option"]:has-text("{option_text}"), li:has-text("{option_text}")').first
                if opt.is_visible(timeout=1000):
                    opt.click()
                    return True
        except Exception:
            continue
    return False


def fill_label(page, labels, value):
    for lab in labels:
        try:
            el = page.get_by_label(lab, exact=False).first
            if el.is_visible(timeout=1200):
                el.fill(value)
                return True
        except Exception:
            continue
    return False


def main():
    if not PW:
        print('PW env missing'); sys.exit(2)
    headful = os.environ.get('HEADFUL') == '1'
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headful,
            args=['--no-sandbox', '--disable-dev-shm-usage',
                  '--disable-blink-features=AutomationControlled'])
        page = browser.new_context(
            locale='en-US', viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36').new_page()
        page.goto('https://www.google.com/', wait_until='domcontentloaded')
        page.wait_for_timeout(1500)
        page.goto('https://accounts.google.com/signup', wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        note('open', page)

        # Step 1: name
        if not fill_label(page, ['First name'], 'yya'):
            try:
                page.locator('input[name="firstName"], #firstName').first.fill('yya')
            except Exception as e:
                note('name-fill-failed', page, str(e))
        click_next(page); page.wait_for_timeout(2500)
        note('after-name', page)

        # Step 2: birthday + gender (custom dropdowns in the new flow)
        fill_label(page, ['Day'], '1')
        fill_label(page, ['Year'], '1997')
        ok_m = pick_dropdown(page, ['Month'], 'January')
        ok_g = pick_dropdown(page, ['Gender', "What's your gender"], 'Male')
        note('birthday-filled', page, f'month_ok={ok_m} gender_ok={ok_g}')
        click_next(page); page.wait_for_timeout(2500)
        note('after-birthday', page)

        # Step 3: username — possibly a choice list first
        try:
            own = page.locator('text=Create your own Gmail address').first
            if own.is_visible(timeout=1500):
                own.click(); page.wait_for_timeout(800)
        except Exception:
            pass
        if not fill_label(page, ['Username'], USERNAME):
            for sel in ['input[name="Username"]', 'input[type="text"]']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.fill(USERNAME); break
                except Exception:
                    continue
        note('username-filled', page)
        click_next(page); page.wait_for_timeout(2500)
        note('after-username', page)

        # Step 4: password
        ok_pw = fill_label(page, ['Create password', 'Password'], PW)
        if not ok_pw:
            try:
                page.locator('input[name="Passwd"]').first.fill(PW)
                ok_pw = True
            except Exception as e:
                note('password-fill-failed', page, str(e))
        fill_label(page, ['Confirm'], PW)
        try:
            page.locator('input[name="PasswdAgain"]').first.fill(PW)
        except Exception:
            pass
        note('password-filled', page, f'pw_ok={ok_pw}')
        click_next(page); page.wait_for_timeout(3500)
        note('after-password', page)

        page.wait_for_timeout(3000)
        note('gate-observed', page)
        browser.close()
    print('DONE')


if __name__ == '__main__':
    main()
