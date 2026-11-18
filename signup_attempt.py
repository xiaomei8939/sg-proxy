#!/usr/bin/env python3
"""Google signup attempt from inside the codespace.

Reads PW from env. Fills name -> birthday/gender -> username -> password,
screenshotting every step into ./shots and writing ./shots/status.json with
the final page's URL and visible text. Stops at whatever gate appears after
the password step (phone verification, same-device check, recovery email,
or terms) without inventing any data.
"""
import json, os, sys, time
from playwright.sync_api import sync_playwright

SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shots')
os.makedirs(SHOTS, exist_ok=True)
PW = os.environ.get('PW', '')
USERNAME = os.environ.get('USERNAME', 'yya249666793')
log = []


def note(step, page, extra=''):
    fn = f'{len(log):02d}-{step}.png'
    try:
        page.screenshot(path=os.path.join(SHOTS, fn))
    except Exception as e:
        fn = f'screenshot-failed: {e}'
    text = ''
    try:
        text = page.locator('body').inner_text(timeout=3000)[:1500]
    except Exception:
        pass
    log.append({'step': step, 'shot': fn, 'url': page.url, 'extra': extra, 'text': text})
    with open(os.path.join(SHOTS, 'status.json'), 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(f'[{step}] {page.url} {extra}', flush=True)


def click_next(page):
    for sel in ['button:has-text("Next")', 'button:has-text("下一步")',
                'span:has-text("Next")']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.click()
                return True
        except Exception:
            continue
    return False


def main():
    if not PW:
        print('PW env missing'); sys.exit(2)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        ctx = browser.new_context(locale='en-US')
        page = ctx.new_page()
        page.goto('https://accounts.google.com/signup', wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        note('open', page)

        # Step 1: name
        try:
            page.locator('input[name="firstName"], #firstName').first.fill('yya')
        except Exception as e:
            note('name-fill-failed', page, str(e))
        click_next(page); page.wait_for_timeout(2500)
        note('after-name', page)

        # Step 2: birthday + gender
        try:
            page.locator('#month').select_option('1')
        except Exception:
            try:
                page.locator('select').first.select_option(index=1)
            except Exception as e:
                note('month-failed', page, str(e))
        for sel, val in [('#day', '1'), ('input[name="day"]', '1'),
                         ('#year', '1997'), ('input[name="year"]', '1997')]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=800):
                    el.fill(val)
            except Exception:
                pass
        try:
            g = page.locator('#gender')
            g.select_option(index=1)  # first real option = Male in en-US flow
        except Exception as e:
            note('gender-failed', page, str(e))
        click_next(page); page.wait_for_timeout(2500)
        note('after-birthday', page)

        # Step 3: username (may offer radio choices first)
        try:
            radios = page.locator('div[role="radio"], input[type="radio"]')
            if radios.count() > 0:
                # choose "Create your own Gmail address" (last radio in en flow)
                radios.last.click()
                page.wait_for_timeout(800)
        except Exception:
            pass
        try:
            u = page.locator('input[name="Username"], input[type="text"]').first
            u.fill(USERNAME)
        except Exception as e:
            note('username-fill-failed', page, str(e))
        click_next(page); page.wait_for_timeout(2500)
        note('after-username', page)

        # Step 4: password
        try:
            page.locator('input[name="Passwd"]').first.fill(PW)
            page.locator('input[name="PasswdAgain"]').first.fill(PW)
        except Exception as e:
            note('password-fill-failed', page, str(e))
        click_next(page); page.wait_for_timeout(3500)
        note('after-password', page)

        # Whatever gate follows: observe only, two beats
        page.wait_for_timeout(3000)
        note('gate-observed', page)
        browser.close()
    print('DONE')


if __name__ == '__main__':
    main()
