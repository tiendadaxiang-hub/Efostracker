from watchlist import agregar_rfc, listar_watchlist, verificar_alertas_watchlist

with open("mis_35_rfcs.csv", "r") as f:
    for linea in f:
        rfc = linea.strip()
        if rfc:
            agregar_rfc(rfc, alias=f"Prov-{rfc[:4]}", categoria="Proveedor")
            
print(f"Total en Radar: {len(listar_watchlist())}")
alertas = verificar_alertas_watchlist()
for a in alertas:
    print(f"ALERTA: {a['alias']} ({a['rfc']}) esta en la lista como {a['situacion']}")
