"""Модуль для обхода Cloudflare через curl_cffi и Playwright.

Реализует два подхода:
1. curl_cffi - эмуляция TLS-отпечатка браузера (быстро, без браузера)
2. Playwright - эмуляция человеческого поведения (медленно, но надёжно)
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Union

from loguru import logger

from core.exceptions import CaptchaError
from core.config import get_settings

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi не установлен. Установите: pip install curl-cffi")


class CaptchaType(Enum):
    TURNSTILE = "turnstile"
    CLOUDFLARE_CHALLENGE = "cf_challenge"
    UNKNOWN = "unknown"


@dataclass
class CaptchaSolution:
    success: bool
    solver_type: str
    solving_time: float
    captcha_type: CaptchaType
    content: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None


class CurlCffiBypass:
    """Обход Cloudflare через curl_cffi с эмуляцией TLS."""

    def __init__(
        self,
        impersonate: str = "chrome110",
        timeout: int = 15,
        proxies: Optional[Dict[str, str]] = None,
    ):
        self.impersonate = impersonate
        self.timeout = timeout
        self.proxies = proxies
        self._session: Optional[curl_requests.Session] = None

        if not CURL_CFFI_AVAILABLE:
            logger.error("curl_cffi не установлен")

    def _get_session(self) -> curl_requests.Session:
        if self._session is None:
            self._session = curl_requests.Session(
                impersonate=self.impersonate,
                timeout=self.timeout,
            )
            if self.proxies:
                self._session.proxies = self.proxies
        return self._session

    def bypass(self, url: str) -> Optional[str]:
        if not CURL_CFFI_AVAILABLE:
            return None

        try:
            session = self._get_session()
            response = session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Sec-Ch-Ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            if response.status_code == 200:
                logger.info(f"curl_cffi: обход успешен для {url}")
                return response.text

            logger.warning(f"curl_cffi: код {response.status_code} для {url}")
            return None

        except Exception as e:
            logger.error(f"curl_cffi: ошибка {e}")
            return None

    def bypass_with_session(self, url: str, api_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not CURL_CFFI_AVAILABLE:
            return None

        try:
            session = self._get_session()

            main_response = session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )

            if main_response.status_code != 200:
                return None

            if api_url:
                api_response = session.get(
                    api_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                        "Accept": "application/json",
                    }
                )

                if api_response.status_code == 200:
                    try:
                        return api_response.json()
                    except Exception:
                        return {"text": api_response.text}

            return {"text": main_response.text, "cookies": session.cookies.get_dict()}

        except Exception as e:
            logger.error(f"curl_cffi сессия: ошибка {e}")
            return None


class CloudflareCaptchaSolver:
    """Солвер Cloudflare через curl_cffi и Playwright."""

    def __init__(
        self,
        use_curl_cffi: bool = True,
        impersonate: str = "chrome110",
        proxies: Optional[Dict[str, str]] = None,
    ):
        self.use_curl_cffi = use_curl_cffi and CURL_CFFI_AVAILABLE

        if self.use_curl_cffi:
            self.curl_bypass = CurlCffiBypass(
                impersonate=impersonate,
                timeout=15,
                proxies=proxies,
            )
        else:
            self.curl_bypass = None

        self.turnstile_selectors = [
            'iframe[src*="turnstile"]',
            'iframe[src*="cloudflare"]',
            '.cf-turnstile',
            '#cf-challenge-wrapper',
            '[data-sitekey]',
            '.turnstile-widget',
        ]

        self.button_selectors = [
            'button[type="submit"]',
            '.cf-submit',
            '.challenge-submit',
            'button:has-text("Verify")',
            'button:has-text("Проверить")',
            'button:has-text("Submit")',
            'button:has-text("Отправить")',
            'button:has-text("I am human")',
            'button:has-text("Я человек")',
        ]

        self._solved_count = 0
        self._last_solve_time: Optional[float] = None

        logger.info(f"CloudflareCaptchaSolver: use_curl_cffi={self.use_curl_cffi}")

    # ==================== curl_cffi методы ====================

    async def solve_with_curl(self, url: str) -> Optional[CaptchaSolution]:
        if not self.use_curl_cffi or not self.curl_bypass:
            return None

        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                self.curl_bypass.bypass,
                url
            )

            solving_time = time.time() - start_time

            if content:
                self._solved_count += 1
                self._last_solve_time = solving_time

                return CaptchaSolution(
                    success=True,
                    solver_type="curl_cffi",
                    solving_time=solving_time,
                    captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
                    content=content,
                )

            return CaptchaSolution(
                success=False,
                solver_type="curl_cffi",
                solving_time=solving_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

        except Exception as e:
            logger.error(f"curl_cffi ошибка: {e}")
            return CaptchaSolution(
                success=False,
                solver_type="curl_cffi",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

    async def solve_with_curl_session(
        self,
        url: str,
        api_url: Optional[str] = None,
    ) -> Optional[CaptchaSolution]:
        if not self.use_curl_cffi or not self.curl_bypass:
            return None

        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.curl_bypass.bypass_with_session,
                url,
                api_url
            )

            solving_time = time.time() - start_time

            if result:
                self._solved_count += 1
                self._last_solve_time = solving_time

                return CaptchaSolution(
                    success=True,
                    solver_type="curl_cffi_session",
                    solving_time=solving_time,
                    captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
                    content=result.get("text"),
                    cookies=result.get("cookies"),
                )

            return CaptchaSolution(
                success=False,
                solver_type="curl_cffi_session",
                solving_time=solving_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

        except Exception as e:
            logger.error(f"curl_cffi сессия ошибка: {e}")
            return CaptchaSolution(
                success=False,
                solver_type="curl_cffi_session",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

    async def test_curl_bypass(self, url: str = "https://nowsecure.nl") -> bool:
        result = await self.solve_with_curl(url)
        return result.success if result else False

    # ==================== Playwright методы ====================

    async def solve_turnstile_with_playwright(self, page) -> CaptchaSolution:
        start_time = time.time()

        try:
            turnstile_iframe = await self._find_turnstile_iframe(page)
            if not turnstile_iframe:
                return CaptchaSolution(
                    success=False,
                    solver_type="playwright_turnstile",
                    solving_time=time.time() - start_time,
                    captcha_type=CaptchaType.TURNSTILE,
                )

            frame = await turnstile_iframe.content_frame()
            if not frame:
                return CaptchaSolution(
                    success=False,
                    solver_type="playwright_turnstile",
                    solving_time=time.time() - start_time,
                    captcha_type=CaptchaType.TURNSTILE,
                )

            await self._random_mouse_movement(page)

            clicked = await self._click_turnstile_element(frame, page, turnstile_iframe)
            if not clicked:
                return CaptchaSolution(
                    success=False,
                    solver_type="playwright_turnstile",
                    solving_time=time.time() - start_time,
                    captcha_type=CaptchaType.TURNSTILE,
                )

            await asyncio.sleep(random.uniform(2, 5))

            if await self._is_captcha_solved(page):
                solving_time = time.time() - start_time
                self._solved_count += 1
                self._last_solve_time = solving_time

                return CaptchaSolution(
                    success=True,
                    solver_type="playwright_turnstile",
                    solving_time=solving_time,
                    captcha_type=CaptchaType.TURNSTILE,
                )

            return CaptchaSolution(
                success=False,
                solver_type="playwright_turnstile",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.TURNSTILE,
            )

        except Exception as e:
            logger.error(f"Turnstile ошибка: {e}")
            return CaptchaSolution(
                success=False,
                solver_type="playwright_turnstile",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.TURNSTILE,
            )

    async def solve_challenge_with_playwright(self, page) -> CaptchaSolution:
        start_time = time.time()

        try:
            if not await self._detect_challenge(page):
                return CaptchaSolution(
                    success=True,
                    solver_type="playwright_challenge",
                    solving_time=0,
                    captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
                )

            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(1, 3))

            verify_button = await self._find_verify_button(page)

            if verify_button:
                await self._human_click(verify_button, page)
                await asyncio.sleep(random.uniform(3, 8))

                if await self._is_challenge_passed(page):
                    solving_time = time.time() - start_time
                    self._solved_count += 1
                    self._last_solve_time = solving_time

                    return CaptchaSolution(
                        success=True,
                        solver_type="playwright_challenge",
                        solving_time=solving_time,
                        captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
                    )

            return await self._solve_challenge_with_reload(page)

        except Exception as e:
            logger.error(f"Challenge ошибка: {e}")
            return CaptchaSolution(
                success=False,
                solver_type="playwright_challenge",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

    async def solve_captcha_with_playwright(self, page) -> CaptchaSolution:
        captcha_type = await self._detect_captcha_type(page)

        if captcha_type == CaptchaType.TURNSTILE:
            return await self.solve_turnstile_with_playwright(page)
        elif captcha_type == CaptchaType.CLOUDFLARE_CHALLENGE:
            return await self.solve_challenge_with_playwright(page)
        else:
            return CaptchaSolution(
                success=False,
                solver_type="playwright_unknown",
                solving_time=0,
                captcha_type=CaptchaType.UNKNOWN,
            )

    # ==================== Вспомогательные методы Playwright ====================

    async def _human_click(self, element, page) -> None:
        box = await element.bounding_box()
        if not box:
            await element.click()
            return

        offset_x = random.uniform(-box['width'] * 0.3, box['width'] * 0.3)
        offset_y = random.uniform(-box['height'] * 0.3, box['height'] * 0.3)
        target_x = box['x'] + box['width'] / 2 + offset_x
        target_y = box['y'] + box['height'] / 2 + offset_y

        await page.mouse.move(
            box['x'] + random.uniform(0, box['width']),
            box['y'] + random.uniform(0, box['height']),
            steps=random.randint(5, 15)
        )

        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.click(target_x, target_y)
        await asyncio.sleep(random.uniform(0.05, 0.15))

    async def _random_mouse_movement(self, page) -> None:
        x = random.randint(100, 1000)
        y = random.randint(100, 600)
        await page.mouse.move(x, y, steps=random.randint(5, 20))
        await asyncio.sleep(random.uniform(0.1, 0.3))

    async def _find_turnstile_iframe(self, page):
        for selector in self.turnstile_selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    return element
            except Exception:
                continue
        return None

    async def _click_turnstile_element(self, frame, page, iframe) -> bool:
        for selector in [
            'input[type="checkbox"]',
            '.turnstile-checkbox',
            '.cf-checkbox',
            'div[role="checkbox"]',
        ]:
            try:
                element = frame.locator(selector)
                if await element.count() > 0:
                    await self._human_click(element, page)
                    return True
            except Exception:
                continue

        for selector in self.button_selectors:
            try:
                element = frame.locator(selector)
                if await element.count() > 0:
                    await self._human_click(element, page)
                    return True
            except Exception:
                continue

        try:
            await self._human_click(iframe, page)
            return True
        except Exception:
            pass

        return False

    async def _find_verify_button(self, page):
        for selector in self.button_selectors:
            try:
                button = page.locator(selector)
                if await button.count() > 0:
                    return button
            except Exception:
                continue
        return None

    async def _detect_challenge(self, page) -> bool:
        if "/cdn-cgi/challenge-platform" in page.url:
            return True

        selectors = [
            '#cf-please-wait',
            '.cf-browser-verification',
            '#challenge-form',
            '.challenge-container',
            'meta[name="cf-challenge"]',
        ]
        for selector in selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return False

    async def _detect_captcha_type(self, page) -> CaptchaType:
        if await self._detect_challenge(page):
            return CaptchaType.CLOUDFLARE_CHALLENGE

        if await self._find_turnstile_iframe(page):
            return CaptchaType.TURNSTILE

        return CaptchaType.UNKNOWN

    async def _is_captcha_solved(self, page) -> bool:
        success_indicators = [
            '.cf-success',
            '.challenge-success',
            'div:has-text("Verification passed")',
            'div:has-text("Проверка пройдена")',
        ]
        for selector in success_indicators:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue

        if "/cdn-cgi/challenge-platform" not in page.url:
            return True

        return False

    async def _is_challenge_passed(self, page) -> bool:
        if "/cdn-cgi/challenge-platform" in page.url:
            return False

        try:
            content = await page.content()
            success_phrases = [
                "verification passed",
                "проверка пройдена",
                "success",
                "успешно",
            ]
            for phrase in success_phrases:
                if phrase.lower() in content.lower():
                    return True
        except Exception:
            pass

        return bool(await page.title())

    async def _solve_challenge_with_reload(self, page) -> CaptchaSolution:
        start_time = time.time()

        try:
            for _ in range(3):
                await self._random_mouse_movement(page)
                await asyncio.sleep(random.uniform(0.5, 1.5))

            await page.reload()
            await asyncio.sleep(random.uniform(2, 4))

            if await self._is_challenge_passed(page):
                return CaptchaSolution(
                    success=True,
                    solver_type="playwright_challenge_reload",
                    solving_time=time.time() - start_time,
                    captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
                )

            return CaptchaSolution(
                success=False,
                solver_type="playwright_challenge_reload",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

        except Exception as e:
            logger.error(f"Перезагрузка ошибка: {e}")
            return CaptchaSolution(
                success=False,
                solver_type="playwright_challenge_reload",
                solving_time=time.time() - start_time,
                captcha_type=CaptchaType.CLOUDFLARE_CHALLENGE,
            )

    # ==================== Универсальный метод ====================

    async def solve(self, url_or_page, api_url: Optional[str] = None) -> Optional[CaptchaSolution]:
        if isinstance(url_or_page, str):
            if api_url:
                return await self.solve_with_curl_session(url_or_page, api_url)
            return await self.solve_with_curl(url_or_page)

        from playwright.async_api import Page
        if isinstance(url_or_page, Page):
            return await self.solve_captcha_with_playwright(url_or_page)

        raise ValueError("Аргумент должен быть URL (str) или страницей Playwright (Page)")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "solved_count": self._solved_count,
            "last_solve_time": self._last_solve_time,
            "use_curl_cffi": self.use_curl_cffi,
            "curl_available": CURL_CFFI_AVAILABLE,
        }


def get_captcha_solver(
    use_curl_cffi: bool = True,
    impersonate: str = "chrome110",
    proxies: Optional[Dict[str, str]] = None,
) -> CloudflareCaptchaSolver:
    return CloudflareCaptchaSolver(
        use_curl_cffi=use_curl_cffi,
        impersonate=impersonate,
        proxies=proxies,
    )


# Для обратной совместимости со старым кодом
class StubCaptchaSolver:
    async def solve_image_captcha(self, image_bytes: bytes) -> str:
        raise CaptchaError("StubCaptchaSolver не используется. Используйте get_captcha_solver()")

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        raise CaptchaError("StubCaptchaSolver не используется. Используйте get_captcha_solver()")