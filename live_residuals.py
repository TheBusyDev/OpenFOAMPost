import matplotlib.pyplot as plt
import glob
import os
import sys
import numpy as np

if len(sys.argv) > 1:
    # Case 1: Argument provided (run from .sh file)
    current_dir = sys.argv[1]
    print(f"Running with case path provided as argument: {current_dir}")
else:
    # Case 2: No argument provided (run directly from terminal)
    current_dir = os.path.dirname(os.path.realpath(__file__))
    print(f"Running from script's location: {current_dir}")

current_folder = os.path.basename(current_dir)


# Costruisci il pattern per il file residuals.dat
pattern = "postProcessing/residuals*/*/residuals.dat"
#pattern = "postProcessing/fluid/residuals*/*/residuals.dat"

# Trova il file corrispondente
filepaths = glob.glob(pattern, recursive=True)
if not filepaths:
    raise FileNotFoundError(f"Nessun file trovato con il pattern: {pattern}")
filepath = filepaths[0]

# Funzione per leggere i dati e l'header dal file
def read_data(filepath):
    with open(filepath, 'r') as file:
        lines = file.readlines()
    
    # Estrai l'header
    header = [line.strip() for line in lines if line.startswith('#')]
    data_lines = [line.split() for line in lines if not line.startswith('#')]

    # Se l'header contiene i nomi delle colonne, estraili
    if len(header) >= 2 and header[-1].startswith('#'):
        field_names = header[-1].replace('#', '').split()
    else:
        raise ValueError("Header con i nomi delle colonne non trovato.")

    # Trasponi per ottenere colonne invece che righe
    transposed_data = list(map(list, zip(*data_lines)))
    
    # Gestisci i valori N/A usando numpy
    try:
        numeric_data = [
            np.array([float(value) if value.lower() != 'n/a' else np.nan for value in column])
            for column in transposed_data
        ]
    except ValueError:
        raise ValueError("Il file contiene valori non convertibili.")

    return field_names, numeric_data

# Creazione del grafico
plt.ion()  # Modalità interattiva per aggiornare dinamicamente il grafico
fig, ax = plt.subplots(figsize=(10, 6))

# Leggi i dati una volta per determinare i nomi dei campi e il numero di colonne
field_names, numeric_data = read_data(filepath)
time_data = numeric_data[0]
columns = numeric_data[1:]  # Escludi la prima colonna (tempo)
field_names = field_names[1:]  # Escludi il nome della colonna temporale

# Crea una linea per ogni colonna
lines = [ax.plot([], [], label=name)[0] for name in field_names]

# Dettagli del grafico
ax.set_yscale('log')  # Scala logaritmica per una migliore visualizzazione
ax.set_xlabel('Tempo')
ax.set_ylabel('Residui')
ax.set_title('Grafico dei residui nel tempo per '+ current_folder)
ax.legend()
ax.grid(True)

# File per salvare il grafico
if not os.path.exists(os.path.join(current_dir, "results")):
    os.makedirs(os.path.join(current_dir, "results"))
output_plot_file = os.path.join(current_dir, "results/residuals_plot.png")

# Aggiorna il grafico in un ciclo
try:
    while True:
        # Leggi i dati dal file
        field_names, numeric_data = read_data(filepath)
        time_data = numeric_data[0]
        columns = numeric_data[1:]

        # Aggiorna i dati nel grafico, gestendo i valori NaN
        for line, column_data in zip(lines, columns):
            line.set_data(time_data, column_data)

        # Aggiorna i limiti degli assi
        ax.relim()  # Ricalcola i limiti
        ax.autoscale_view()  # Aggiorna la visualizzazione

        # Ridisegna il grafico
        plt.pause(1)  # Pausa per un secondo per permettere l'aggiornamento del grafico

        # Verifica se la finestra è stata chiusa, in tal caso salva e termina
        if not plt.fignum_exists(fig.number):
            print(f"\nFinestra del grafico chiusa. \nSalvataggio del grafico in: \n{output_plot_file}\n\n")
            fig.savefig(output_plot_file)  # Salva il grafico come file PNG
            break
except KeyboardInterrupt:
    print("\nScript interrotto.\n\n")
    fig.savefig(output_plot_file)
    print(f"Grafico salvato in {output_plot_file}\n\n")

# Chiudi il grafico
plt.close(fig)

