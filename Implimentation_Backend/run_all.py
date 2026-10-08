import subprocess
import time
import logging
import sys
import os

# Konfiguration des Loggings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def run_script(script_name):
    """
    Führt ein Python-Skript als isolierten Unterprozess aus.
    Dies garantiert eine saubere Speicherfreigabe (Garbage Collection)
    auf Betriebssystemebene nach jedem rechenintensiven Schritt.
    """
    if not os.path.exists(script_name):
        logging.error(f"Kritischer Fehler: Datei '{script_name}' nicht gefunden.")
        sys.exit(1)

    logging.info(f"=== Starte Pipeline-Schritt: {script_name} ===")
    start_time = time.time()
    
    try:
        # sys.executable stellt sicher, dass exakt dieselbe Python-Umgebung (venv) genutzt wird
        subprocess.run([sys.executable, script_name], check=True)
        elapsed = time.time() - start_time
        logging.info(f"=== {script_name} erfolgreich beendet nach {elapsed:.1f} Sekunden ===\n")
    except subprocess.CalledProcessError as e:
        logging.error(f"Abbruch: Fehler bei der Ausführung von {script_name} (Exit Code {e.returncode})")
        sys.exit(1)

def main():
    logging.info("Starte vollständige Berechnungspipeline (Schritte 2 bis 10)...")
    total_start = time.time()
    
    # Definition der exakten Ausführungsreihenfolge gemäß Spezifikation
    skripte = [
        "build_grid.py",  # Schritt 2: Zensus und POIs auf das H3-Raster mappen
        "model.py",       # Schritte 3 bis 8: Topologie, Nachfrage, Affinität und Huff-Modell
        "luecke.py",      # Schritt 8a: Angebotslücke als Residuum (GLM-Regression)
        "robustness.py",  # Schritt 9: Monte-Carlo Simulation für Stabilität
        "portfolio.py"    # Schritt 10: Submodulare Maximierung für das Filialnetz
    ]
    
    for skript in skripte:
        run_script(skript)
        
    total_elapsed = time.time() - total_start
    logging.info(f"Pipeline vollständig und fehlerfrei durchlaufen in {total_elapsed:.1f} Sekunden.")
    logging.info("Alle Output-Dateien (*_scored.csv, *_portfolio.csv, *_modell.json) liegen in data/")
    logging.info("Die Daten sind nun bereit. Starte das Dashboard mit: streamlit run app.py")

if __name__ == "__main__":
    main()