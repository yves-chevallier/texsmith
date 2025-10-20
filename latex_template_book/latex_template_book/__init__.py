from importlib.resources import files

def get_template_path() -> str:
    # Retourne un chemin réel vers le dossier "template"
    return str(files(__package__) / "template")
