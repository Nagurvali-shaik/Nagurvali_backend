
from .models import *


class InventoryService:
    
    @staticmethod
    def reserve_stock(inventory: Inventory, qty: int, reason="Order Reserved") -> bool:
        if inventory.quantity_available >= qty:
            inventory.quantity_available -= qty
            inventory.quantity_reserved += qty
            inventory.save()
            StockMovement.objects.create(
                inventory=inventory,
                quantity=-qty,
                reason=reason
            )
            return True
        return False

    @staticmethod
    def release_stock(inventory: Inventory, qty: int, reason="Order Released"):
        inventory.quantity_reserved -= qty
        inventory.quantity_available += qty
        inventory.save()
        StockMovement.objects.create(
            inventory=inventory,
            quantity=qty,
            reason=reason
        )

    @staticmethod
    def confirm_stock(inventory: Inventory, qty: int, reason="Order Confirmed"):
        # Move reserved stock to sold / shipped
        inventory.quantity_reserved -= qty
        inventory.save()
        StockMovement.objects.create(
            inventory=inventory,
            quantity=-qty,
            reason=reason
        )

    @staticmethod
    def adjust_stock(inventory: Inventory, qty: int, reason="Manual Adjustment"):
        # Positive qty = stock_in, Negative qty = stock_out
        inventory.quantity_available += qty
        inventory.save()
        StockMovement.objects.create(
            inventory=inventory,
            quantity=qty,
            reason=reason
        )


class StockManager:

    @staticmethod
    def allocate_order(variant: ProductVariant, qty: int):
        # Example: find inventory across locations
        inventories = Inventory.objects.filter(variant=variant).order_by("quantity_available")
        allocated = 0
        for inv in inventories:
            if inv.quantity_available <= 0:
                continue
            take_qty = min(qty - allocated, inv.quantity_available)
            InventoryService.reserve_stock(inv, take_qty, reason="Order Allocation")
            allocated += take_qty
            if allocated >= qty:
                break
        if allocated < qty:
            raise Exception("Not enough stock to fulfill order")

    @staticmethod
    def release_order(variant: ProductVariant, qty: int):
        # Find reserved stock and release
        inventories = Inventory.objects.filter(variant=variant).filter(quantity_reserved__gt=0)
        released = 0
        for inv in inventories:
            take_qty = min(qty - released, inv.quantity_reserved)
            InventoryService.release_stock(inv, take_qty, reason="Order Release")
            released += take_qty
            if released >= qty:
                break
        if released < qty:
            raise Exception("Not enough reserved stock to release order")

    @staticmethod
    def confirm_order(variant: ProductVariant, qty: int):
        # Consume reserved stock after payment confirmation
        inventories = Inventory.objects.filter(variant=variant).filter(quantity_reserved__gt=0)
        confirmed = 0
        for inv in inventories:
            if inv.quantity_reserved <= 0:
                continue
            take_qty = min(qty - confirmed, inv.quantity_reserved)
            InventoryService.confirm_stock(inv, take_qty, reason="Order Confirmed")
            confirmed += take_qty
            if confirmed >= qty:
                break
        if confirmed < qty:
            raise Exception("Not enough reserved stock to confirm order")
