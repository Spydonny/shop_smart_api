import re
import os
import uuid
from typing import Union, List

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from google import genai

import models as mdl

# Инициализируем клиент один раз на старте
API_KEY = "AIzaSyD37DxJHxWSQ6ZrLSy7lfQOGXsUUBEcPFg"

async def get_generated_items(request: mdl.GenerationRequest) -> List[mdl.ItemDB]:

    prompt_with_format = (
        request.prompt
        + "\n\nНапиши ответ в формате\n"
        "NAME_OF_PRODUCT:QUANTITY:PRICE;NAME2:QUANTITY2:PRICE2;...\n\n"
        "Где QUANTITY — целое число, а PRICE — число (целое или с десятичной частью) в тенге без символов. "
        "Не пиши ничего кроме этого формата. Все выведенные числа должны быть челочисленные\n"
        "Пример: Гречка 1кг:1:500;Масло подсолнечное 1л:2:1000;Рис 1кг:3:1500\n\n"
    )
    client = genai.Client(api_key=API_KEY)

    try:
        resp = await run_in_threadpool(
            client.models.generate_content,
            model='gemini-2.0-flash',
            contents=prompt_with_format,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка Gemini API: {e}"
        )

    raw = resp.text.strip()
    entries = re.split(r"\s*;\s*", raw)
    items: List[mdl.ItemDB] = []

    for entry in entries:
        m = re.match(
            r"\s*([^:]+)\s*:\s*(\d+)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$",
            entry
        )
        if not m:
            return raw  # неожиданный формат — возвращаем сырой текст

        title = m.group(1).strip()
        quantity = int(m.group(2))
        price = float(m.group(3))

        item = mdl.ItemDB(
            id=uuid.uuid4(),
            title=title,
            quantity=quantity,
            price=price,
            is_bought=False
        )
        items.append(item)

    return items


async def get_product_price(product_name: str) -> float:
    prompt_text = (
        f"Пожалуйста, укажи примерную цену для продукта: {product_name} "
        "в тенге, только число без валютных обозначений. "
        "Ответь в формате: ЦЕНА ПРОДУКТА"
    )

    client = genai.Client(api_key=API_KEY)

    try:
        resp = await run_in_threadpool(
            client.models.generate_content,
            model='gemini-2.0-flash',
            contents=prompt_text,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка Gemini API: {e}"
        )

    # Извлекаем текст из ответа
    try:
        text = resp.candidates[0].content.parts[0].text.strip()
    except (AttributeError, IndexError):
        text = getattr(resp, 'text', '').strip()

    # Извлекаем число (целое или с десятичной частью)
    match = re.search(r"\d+(?:[.,]\d+)?", text.replace(" ", ""))
    if match:
        price_str = match.group(0).replace(",", ".")
        try:
            return float(price_str)
        except ValueError:
            pass

    return 777.0  # fallback значение, если парсинг не удался