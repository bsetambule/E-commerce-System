from app.extensions import db
from app.models import (
    BranchProduct,
    BranchProductVariant,
    ProductVariant,
    Inventory
)

class StoreManagerService:

    @staticmethod
    def get_branch_product(branch_id: int, product_id: int):
        return BranchProduct.query.filter_by(
            branch_id=branch_id,
            product_id=product_id
        ).first()

    @staticmethod
    def get_or_create_branch_variant(branch_product, variant):
        bv = StoreManagerService.get_branch_variant(branch_product, variant)

        if bv:
            return bv

        bv = BranchProductVariant(
            branch_product_id=branch_product.id,
            variant_id=variant.id,
            is_available=True,
            allows_pickup=True,
            allows_delivery=True
        )

        db.session.add(bv)
        return bv

    @staticmethod
    def ensure_inventory(branch_variant):

        if branch_variant.inventory:
            return branch_variant.inventory

        inventory = Inventory(
            branch_variant_id=branch_variant.id,
            quantity=0,
            reserved_quantity=0
        )

        db.session.add(inventory)
        return inventory