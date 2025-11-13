from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_panel' 
    
    def ready(self):
        # Import signal handlers to wire up TransactionItem -> InventoryHistory actions
        try:
            import admin_panel.signals  # noqa: F401
        except Exception:
            # Avoid raising on app import; errors will show during runtime if signals fail
            pass
