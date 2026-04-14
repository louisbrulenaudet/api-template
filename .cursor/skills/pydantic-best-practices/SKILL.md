---
name: pydantic-best-practices
description: Pydantic v2 performance best practices. Use when writing or reviewing Pydantic models, TypeAdapters, validators, or union types. Avoids common pitfalls that silently degrade validation throughput.
---

# Pydantic Best Practices

Official Pydantic performance skill. Apply when writing new models or reviewing existing ones.

## Prefer `model_validate_json()` over `model_validate(json.loads(...))`

`model_validate(json.loads(...))` parses JSON in Python, converts to a dict, then validates. `model_validate_json()` validates directly from the raw JSON string inside Rust — skip the intermediate dict entirely.

```python
import json
from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str


raw = '{"id": 1, "name": "Alice"}'

# DO NOT DO THIS
user = User.model_validate(json.loads(raw))

# Do this
user = User.model_validate_json(raw)
```

**Exception**: when using a `'before'` or `'wrap'` validator on the model, the two-step method can be faster. Benchmark before assuming.

## Instantiate `TypeAdapter` once, not per call

Every `TypeAdapter(...)` call builds a new validator and serializer. Move it to module level or a class attribute.

```python
from pydantic import TypeAdapter

# DO NOT DO THIS
def parse_ids(data: list) -> list[int]:
    adapter = TypeAdapter(list[int])
    return adapter.validate_python(data)

# Do this
_ids_adapter = TypeAdapter(list[int])

def parse_ids(data: list) -> list[int]:
    return _ids_adapter.validate_python(data)
```

## Use concrete types instead of abstract collections

`Sequence` forces an `isinstance` check and tries multiple concrete types. `Mapping` does the same. Use `list`, `tuple`, or `dict` when you know the exact type.

```python
from collections.abc import Mapping, Sequence
from pydantic import BaseModel


# DO NOT DO THIS
class SlowModel(BaseModel):
    items: Sequence[int]
    meta: Mapping[str, str]


# Do this
class FastModel(BaseModel):
    items: list[int]
    meta: dict[str, str]
```

## Use `Any` when validation is not needed

Pydantic skips all validation for `Any` fields. Use it when the value is already trusted or will be validated elsewhere.

```python
from typing import Any
from pydantic import BaseModel


class Event(BaseModel):
    name: str
    payload: Any  # raw blob, no validation cost
```

## Avoid subclassing primitives for extra attributes

Pydantic must inspect subclasses of primitives specially. Carry extra state in a model field instead.

```python
from pydantic import BaseModel


# DO NOT DO THIS
class CompletedStr(str):
    def __init__(self, s: str):
        self.s = s
        self.done = False


# Do this
class Task(BaseModel):
    value: str
    done: bool = False
```

## Use discriminated (tagged) unions over plain unions

Plain unions try each branch in order. A discriminated union resolves the type in O(1) via a `Literal` discriminator field.

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class DivModel(BaseModel):
    el_type: Literal['div'] = 'div'
    class_name: str | None = None
    children: list[Any] | None = None


class SpanModel(BaseModel):
    el_type: Literal['span'] = 'span'
    class_name: str | None = None
    contents: str | None = None


class ButtonModel(BaseModel):
    el_type: Literal['button'] = 'button'
    class_name: str | None = None
    contents: str | None = None


class InputModel(BaseModel):
    el_type: Literal['input'] = 'input'
    class_name: str | None = None
    value: str | None = None


# DO NOT DO THIS
class HtmlSlow(BaseModel):
    contents: DivModel | SpanModel | ButtonModel | InputModel


# Do this
class Html(BaseModel):
    contents: DivModel | SpanModel | ButtonModel | InputModel = Field(
        discriminator='el_type'
    )
```

## Use `TypedDict` over nested models for inner structures

`TypedDict` has lower overhead than a full `BaseModel` when the inner structure doesn't need methods, validators, or serialization customisation.

```python
from typing import TypedDict
from pydantic import BaseModel


# Prefer this for nested, plain data shapes
class Address(TypedDict):
    street: str
    city: str
    zip_code: str


class User(BaseModel):
    name: str
    address: Address
```

## Avoid `wrap` validators on hot paths

Wrap validators materialise data as Python objects during validation, bypassing the Rust-side fast path. Prefer `before`, `after`, or `field_validator` modes.

```python
from pydantic import BaseModel, field_validator


# Avoid on hot paths
# @model_validator(mode='wrap')
# def validate_model(cls, value, handler): ...

# Prefer
class Order(BaseModel):
    amount: float

    @field_validator('amount')
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('amount must be positive')
        return v
```

## Use `FailFast` on sequences to short-circuit on first error

Available from Pydantic v2.8+. Trades full error visibility for reduced work when early rejection is acceptable.

```python
from typing import Annotated
from pydantic import FailFast, TypeAdapter, ValidationError

_bool_list_adapter = TypeAdapter(Annotated[list[bool], FailFast()])

try:
    _bool_list_adapter.validate_python([True, 'invalid', False, 'also invalid'])
except ValidationError as exc:
    # Only the first error is reported — stops after 'invalid'
    print(exc)
```

Do not apply `FailFast` when you need to surface all validation errors to an end user.
