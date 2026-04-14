from fastapi import APIRouter

router = APIRouter(prefix="/api/offertes", tags=["offertes"])


@router.get("")
def get_offertes():
    return {
        "items": [
            {
                "id": "off_001",
                "code": "Q-001",
                "klant_naam": "Johan",
                "omschrijving": "Buitenschilderwerk woonhuis",
                "bedrag": 1375.0,
                "status": "wordt_voorbereid",
            }
        ],
        "total": 1,
    }
