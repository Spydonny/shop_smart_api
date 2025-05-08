# main.py
from fastapi import FastAPI, HTTPException,  Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from typing import  Dict, Any
from uuid import uuid4, UUID
import motor.motor_asyncio

import models as mdl

# MongoDB setup
MONGO_DETAILS = "mongodb://localhost:27017"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
db = client.shared_lists

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
async def create_list(name: str = Field("New List")):
    list_id = uuid4()
    new_list = {"id": list_id.hex, "name": name, "items": []}
    await db.lists.insert_one(new_list)
    return {"id": list_id}

@app.get("/api/lists/{list_id}", response_model=mdl.ListDB)
async def read_list(list_id: UUID = Path(...)):
    doc = await get_list_or_404(list_id)
    items = [mdl.ItemDB(id=UUID(item['id']), title=item['title'], quantity=item['quantity']) for item in doc['items']]
    return mdl.ListDB(id=UUID(doc['id']), name=doc['name'], items=items)

@app.get("/api/lists/{list_id}/poll", response_model=mdl.ListDB)
async def poll_list(list_id: UUID = Path(...)):
    # return latest list for polling
    doc = await get_list_or_404(list_id)
    items = [mdl.ItemDB(id=UUID(item['id']), title=item['title'], quantity=item['quantity']) for item in doc['items']]
    return mdl.ListDB(id=UUID(doc['id']), name=doc['name'], items=items)

@app.post("/api/lists/{list_id}/items", status_code=201)
async def add_item(
    item: mdl.ItemCreate,
    list_id: UUID = Path(...)
):
    doc = await get_list_or_404(list_id)
    item_id = uuid4()
    item_dict = {"id": item_id.hex, "title": item.title, "quantity": item.quantity}
    await db.lists.update_one(
        {"id": list_id.hex},
        {"$push": {"items": item_dict}}
    )
    return {"id": item_id}

@app.put("/api/lists/{list_id}/items/{item_id}")
async def update_item(
    item: mdl.ItemCreate,
    list_id: UUID = Path(...),
    item_id: UUID = Path(...)
):
    doc = await get_list_or_404(list_id)
    # check exists
    exists = any(i['id']==item_id.hex for i in doc['items'])
    if not exists:
        raise HTTPException(404, "Item not found")
    await db.lists.update_one(
        {"id": list_id.hex, "items.id": item_id.hex},
        {"$set": {"items.$.title": item.title, "items.$.quantity": item.quantity}}
    )
    return {"status": "ok"}

@app.delete("/api/lists/{list_id}/items/{item_id}", status_code=204)
async def delete_item(
    list_id: UUID = Path(...),
    item_id: UUID = Path(...)
):
    doc = await get_list_or_404(list_id)
    await db.lists.update_one(
        {"id": list_id.hex},
        {"$pull": {"items": {"id": item_id.hex}}}
    )
    return

# Run uvicorn if main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
