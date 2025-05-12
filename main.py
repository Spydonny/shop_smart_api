from fastapi import FastAPI, HTTPException,  Path
from fastapi.middleware.cors import CORSMiddleware
from typing import  Dict, Any, List
from uuid import uuid4, UUID
import motor.motor_asyncio
import asyncio
from datetime import datetime

import models as mdl

# MongoDB setup
MONGO_DETAILS = "mongodb://localhost:27017"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
db = client.shopping_lists

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_list_or_404(list_id: UUID) -> Dict[str, Any]:
    doc = await db.lists.find_one({"id": list_id.hex})
    if not doc:
        raise HTTPException(404, "List not found")
    return doc

@app.post("/api/lists", status_code=201)
async def create_list(data: mdl.ListCreate):
    list_id = uuid4()
    updated_at = datetime.now().timestamp()
    new_list = {"id": list_id.hex, "name": data.name, "items": [], "updated_at": updated_at}
    await db.lists.insert_one(new_list)
    return {"id": list_id}

@app.get("/api/lists/{list_id}", response_model=mdl.ListDB)
async def read_list(list_id: UUID = Path(...)):
    doc = await get_list_or_404(list_id)
    items = [mdl.ItemDB(id=UUID(item['id']), title=item['title'], quantity=item['quantity'], price=item['price'], is_bought=item['is_bought']) for item in doc['items']]
    return mdl.ListDB(id=UUID(doc['id']), name=doc['name'], items=items, updated_at=doc["updated_at"],)

@app.get("/api/lists", response_model=List[mdl.ListDB])
async def read_lists():
    cursor = db.lists.find()
    lists: List[mdl.ListDB] = []
    async for doc in cursor:
        items: List[mdl.ItemDB] = []
        for item in doc.get("items", []):
            # если price нет — подставляем 0.0
            price = item.get("price", 0.0)
            items.append(
                mdl.ItemDB(
                    id=UUID(item["id"]),
                    title=item["title"],
                    quantity=item["quantity"],
                    price=price,
                    is_bought=item["is_bought"]
                )
            )
        lists.append(
            mdl.ListDB(
                id=UUID(doc["id"]),
                name=doc["name"],
                items=items,
                updated_at = doc["updated_at"],
            )
        )
    return lists

@app.get("/api/lists/{list_id}/poll", response_model=mdl.ListDB)
async def poll_list(
    list_id: UUID = Path(...),
    last_updated: float = 0.0
):
    TIMEOUT_SECONDS = 20
    CHECK_INTERVAL = 1
    start_time = datetime.now().timestamp()

    async def has_changed(since: float) -> bool:
        doc = await get_list_or_404(list_id)
        return doc.get("updated_at", 0) > since

    while True:
        if await has_changed(last_updated):
            doc = await get_list_or_404(list_id)

            # Build your items, knowing is_bought will default to False if missing
            items = [
                mdl.ItemDB(
                    id=UUID(item["id"]),
                    title=item["title"],
                    quantity=item["quantity"],
                    price=item.get("price", 0.0),
                    is_bought=item.get("is_bought", False),
                )
                for item in doc.get("items", [])
            ]

            return mdl.ListDB(
                id=UUID(doc["id"]),
                name=doc["name"],
                items=items,
                updated_at=doc["updated_at"],
            )

        if datetime.now().timestamp() - start_time > TIMEOUT_SECONDS:
            raise HTTPException(status_code=204, detail="No changes")

        await asyncio.sleep(CHECK_INTERVAL)


@app.delete("/api/lists/{list_id}", status_code=204)
async def delete_list(list_id: UUID = Path(...)):
    doc = await get_list_or_404(list_id)
    await db.lists.delete_one({"id": doc['id']})
    return

@app.post("/api/lists/{list_id}/items", status_code=201)
async def add_item(
    item: mdl.ItemCreate,
    list_id: UUID = Path(...)
):
    import ext_api

    _ = await get_list_or_404(list_id)
    item_id = uuid4()
    item_price = await ext_api.get_product_price(item.title)
    item_dict = {"id": item_id.hex, "title": item.title, "quantity": item.quantity, "price": item_price, "is_bought": False}
    await db.lists.update_one(
        {"id": list_id.hex},
        {"$push": {"items": item_dict}}
    )
    return {"id": item_id}

@app.put("/api/lists/{list_id}/items/{item_id}")
async def update_item(
    item: mdl.ItemUpdate,
    list_id: UUID = Path(...),
    item_id: UUID = Path(...)
):
    result = await db.lists.update_one(
        {"id": list_id.hex},
        {
            "$set": {

                "items.$[elem].title": item.title,
                "items.$[elem].quantity": item.quantity,
                "items.$[elem].is_bought": bool(item.is_bought)
            }
        },
        array_filters=[{"elem.id": item_id.hex}]
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"status": "ok"}


@app.delete("/api/lists/{list_id}/items/{item_id}", status_code=204)
async def delete_item(
    list_id: UUID = Path(...),
    item_id: UUID = Path(...)
):
    _ = await get_list_or_404(list_id)
    await db.lists.update_one(
        {"id": list_id.hex},
        {"$pull": {"items": {"id": item_id.hex}}}
    )
    return

@app.post("/api/lists/{list_id}/generate_items", response_model=mdl.ListDB)
async def generate_text(
        request: mdl.GenerationRequest,
        list_id: UUID = Path(...),
    ):
    import ext_api
    items_or_raw = await ext_api.get_generated_items(request)

    _ = await get_list_or_404(list_id)

    if isinstance(items_or_raw, str):
    # parsing failed → raw text for debug:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned unexpected format: {items_or_raw}"
        )
    
    items: List[mdl.ItemDB] = items_or_raw

    for item in items:
        await db.lists.update_one(
            {"id": list_id.hex},
            {"$push": {
                "items": {
                    "id": item.id.hex,
                    "title": item.title,
                    "quantity": item.quantity,
                    "price": item.price,
                    "is_bought": False
                }
            }}
        )

    doc = await db.lists.find_one({"id": list_id.hex})
    return doc

if __name__ == "__main__":
    # Run the FastAPI app

    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
