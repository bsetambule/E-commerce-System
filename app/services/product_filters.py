from sqlalchemy import or_
from app.models.product import Product
from app.models.branchproductvariant import BranchProductVariant
from app.models.inventory import Inventory
from app.models.productvariant import ProductVariant


def apply_product_tab_filter(query, tab, branch_id):

    if tab == "all":
        return query

    # join once when needed
    query = query.join(Product.variants)\
                 .join(ProductVariant.branch_variants)

    bpv = BranchProductVariant
    inv = Inventory

    if tab == "available":
        return query.filter(
            bpv.branch_product.has(branch_id=branch_id),
            bpv.is_available.is_(True)
        ).distinct()

    if tab == "lowstock":
        return query.join(bpv.inventory).filter(
            bpv.branch_product.has(branch_id=branch_id),
            inv.quantity.between(1, 5)
        ).distinct()

    if tab == "outofstock":
        return query.outerjoin(bpv.inventory).filter(
            bpv.branch_product.has(branch_id=branch_id),
            or_(
                inv.quantity <= 0,
                inv.id.is_(None)
            )
        ).distinct()

    return query