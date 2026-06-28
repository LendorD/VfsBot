"""Тесты для Cloudflare капчи солвера."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import Page

from browser.captcha_solver import (
    CloudflareCaptchaSolver,
    CaptchaType,
    CaptchaSolution,
    HumanEmulator,
    get_captcha_solver,
    CaptchaError,
)


@pytest.mark.asyncio
async def test_human_emulator_click():
    """Тест эмуляции клика человека."""
    mock_page = AsyncMock()
    mock_element = AsyncMock()
    mock_element.bounding_box = AsyncMock(return_value={
        'x': 100, 'y': 100, 'width': 50, 'height': 30
    })
    
    await HumanEmulator.human_click(mock_element, mock_page)
    
    # Проверяем, что были вызовы
    mock_page.mouse.move.assert_called_once()
    mock_page.mouse.click.assert_called_once()


@pytest.mark.asyncio
async def test_detect_captcha_type():
    """Тест определения типа капчи."""
    solver = CloudflareCaptchaSolver()
    mock_page = AsyncMock()
    
    # Тест Turnstile
    mock_page.locator.return_value.count = AsyncMock(return_value=1)
    assert await solver.detect_captcha_type(mock_page) == CaptchaType.TURNSTILE
    
    # Тест Cloudflare Challenge
    with patch.object(solver, '_detect_cloudflare_challenge', AsyncMock(return_value=True)):
        assert await solver.detect_captcha_type(mock_page) == CaptchaType.CLOUDFLARE_CHALLENGE


@pytest.mark.asyncio
async def test_solve_turnstile():
    """Тест решения Turnstile."""
    solver = CloudflareCaptchaSolver()
    mock_page = AsyncMock()
    
    # Мокаем поиск iframe
    mock_iframe = AsyncMock()
    mock_iframe.content_frame = AsyncMock(return_value=AsyncMock())
    mock_page.locator.return_value.first = mock_iframe
    mock_page.locator.return_value.count = AsyncMock(return_value=1)
    
    # Мокаем is_captcha_solved
    solver.is_captcha_solved = AsyncMock(return_value=True)
    
    # Мокаем HumanEmulator
    with patch.object(HumanEmulator, 'human_click', AsyncMock()):
        result = await solver.solve_cloudflare_turnstile(mock_page)
        
        assert isinstance(result, CaptchaSolution)
        assert result.captcha_type == CaptchaType.TURNSTILE
        assert result.solver_type == "cloudflare_turnstile_human"


@pytest.mark.asyncio
async def test_solve_challenge():
    """Тест решения Cloudflare Challenge."""
    solver = CloudflareCaptchaSolver()
    mock_page = AsyncMock()
    
    # Мокаем детект challenge
    solver._detect_cloudflare_challenge = AsyncMock(return_value=True)
    
    # Мокаем is_challenge_passed
    solver.is_challenge_passed = AsyncMock(return_value=True)
    
    # Мокаем HumanEmulator
    with patch.object(HumanEmulator, 'human_click', AsyncMock()):
        result = await solver.solve_cloudflare_challenge(mock_page)
        
        assert isinstance(result, CaptchaSolution)
        assert result