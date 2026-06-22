"""Браузерный слой: управление Playwright и клиент VFS Global."""

from browser.captcha_solver import CaptchaSolver, get_captcha_solver
from browser.client import AvailableSlot, BookingResult, VFSClient
from browser.manager import BrowserManager

__all__ = [
    "CaptchaSolver",
    "get_captcha_solver",
    "AvailableSlot",
    "BookingResult",
    "VFSClient",
    "BrowserManager",
]
