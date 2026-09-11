"""Liste des valeurs surveillées (composition indicative du CAC 40).

La composition officielle du CAC 40 est revue chaque trimestre par Euronext :
https://live.euronext.com/en/product/indices/FR0003500008-XPAR

Cette liste peut donc devenir légèrement obsolète avec le temps (une valeur
retirée de l'indice, une autre ajoutée). Ce n'est pas grave pour le
fonctionnement du programme : il continuera simplement à analyser les
valeurs listées ici. Pour la mettre à jour, il suffit d'ajouter ou de
supprimer une ligne ci-dessous (aucune compétence de développeur requise) :

    ("TICKER.PA", "Nom de l'entreprise"),

Le ticker doit être au format utilisé par Yahoo Finance (généralement le
code Euronext Paris suivi de ".PA").
"""

CAC40_TICKERS = [
    ("AI.PA", "Air Liquide"),
    ("AIR.PA", "Airbus"),
    ("MT.AS", "ArcelorMittal"),
    ("CS.PA", "AXA"),
    ("BNP.PA", "BNP Paribas"),
    ("EN.PA", "Bouygues"),
    ("CAP.PA", "Capgemini"),
    ("CA.PA", "Carrefour"),
    ("ACA.PA", "Crédit Agricole"),
    ("BN.PA", "Danone"),
    ("DSY.PA", "Dassault Systèmes"),
    ("EDEN.PA", "Edenred"),
    ("ENGI.PA", "Engie"),
    ("EL.PA", "EssilorLuxottica"),
    ("ERF.PA", "Eurofins Scientific"),
    ("RMS.PA", "Hermès International"),
    ("KER.PA", "Kering"),
    ("OR.PA", "L'Oréal"),
    ("LR.PA", "Legrand"),
    ("MC.PA", "LVMH"),
    ("ML.PA", "Michelin"),
    ("ORA.PA", "Orange"),
    ("RI.PA", "Pernod Ricard"),
    ("PUB.PA", "Publicis Groupe"),
    ("RNO.PA", "Renault"),
    ("SAF.PA", "Safran"),
    ("SGO.PA", "Saint-Gobain"),
    ("SAN.PA", "Sanofi"),
    ("SU.PA", "Schneider Electric"),
    ("GLE.PA", "Société Générale"),
    ("STLAP.PA", "Stellantis"),
    ("STMPA.PA", "STMicroelectronics"),
    ("TEP.PA", "Teleperformance"),
    ("HO.PA", "Thales"),
    ("TTE.PA", "TotalEnergies"),
    ("URW.PA", "Unibail-Rodamco-Westfield"),
    ("VIE.PA", "Veolia"),
    ("DG.PA", "Vinci"),
    ("WLN.PA", "Worldline"),
]
