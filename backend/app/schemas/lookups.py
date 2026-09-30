from pydantic import BaseModel, ConfigDict


class Option(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ModuleOption(Option):
    url_prefix: str


class LookupsOut(BaseModel):
    institutes: list[Option]
    approval_sections: list[Option]
    erp_modules: list[ModuleOption]
    developers: list[Option]
