from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unified_config.core.config_manager import ConfigManager

from models.function import FunctionModel
from schemas.schemas import FunctionCreate, FunctionResponse


async def get_all_functions(db: AsyncSession, config_manager: ConfigManager):
    """Retrieve all stored functions, checking if functions are enabled."""
    functions_enabled = await config_manager.get_config("functions", "enabled")

    if not functions_enabled:
        raise HTTPException(
            status_code=403, detail="Function management is disabled by config."
        )

    result = await db.execute(select(FunctionModel))
    functions = result.scalars().all()
    return [
        FunctionResponse(id=f.id, name=f.name, description=f.description)
        for f in functions
    ]


async def add_function(
    db: AsyncSession, config_manager: ConfigManager, function_data: FunctionCreate
):
    """Add a new function, checking if function creation is allowed."""
    functions_enabled = await config_manager.get_config("functions", "enabled")

    if not functions_enabled:
        raise HTTPException(
            status_code=403, detail="Function creation is disabled by config."
        )

    existing_function = await db.execute(
        select(FunctionModel).where(FunctionModel.name == function_data.name)
    )
    if existing_function.scalars().first():
        raise HTTPException(
            status_code=400, detail="Function with this name already exists."
        )

    new_function = FunctionModel(
        name=function_data.name, description=function_data.description
    )
    db.add(new_function)
    await db.commit()
    await db.refresh(new_function)

    return FunctionResponse(
        id=new_function.id, name=new_function.name, description=new_function.description
    )


async def delete_function_by_name(
    db: AsyncSession, config_manager: ConfigManager, name: str
):
    """Delete a function by name, checking if deletion is allowed."""
    functions_enabled = await config_manager.get_config("functions", "enabled")

    if not functions_enabled:
        raise HTTPException(
            status_code=403, detail="Function deletion is disabled by config."
        )

    result = await db.execute(select(FunctionModel).where(FunctionModel.name == name))
    function = result.scalars().first()

    if not function:
        raise HTTPException(status_code=404, detail="Function not found.")

    await db.delete(function)
    await db.commit()
    return {"message": f"Function '{name}' deleted successfully"}
