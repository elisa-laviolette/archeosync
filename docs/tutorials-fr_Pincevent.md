# La préparation d'un relevé de mètre carré

- Trouver le prochain numéro d'objet et le bon niveau de relevé ('a', 'b', 'c', etc.)
- Ouvrir le projet QGIS `Pincevent`
- Dans la couche `Mètres carrés SCR local`, sélectionner les mètres carrés à préparer
- Menu `Extension`>`ArcheoSync`>`Préparer l'enregistrement`
- Dans la liste des mètres carrés sélectionnés, régler pour chacun le prochain numéro et le niveau à démonter, et choisir l'orthophoto de fond
- Cliquer sur `Préparer l'enregistrement`
- Attendre ; ça prend un peu de temps surtout si l'orthophoto de fond est lourde
- Les projets de terrain sont créés dans le dossier de destination choisi dans la configuration (`Dossier de destination des projets de terrain`)
- Transférer les dossiers de terrain sur les tablettes

# Le relevé de mètre carré

- Ouvrir le projet de terrain (fichier `.qgs`) avec QGIS 3.40
- Pour se placer au bon endroit, appuyer longuement sur la couche raster `Background` ou sur la couche `Mètres carrés` et cliquer sur `Zoomer sur la couche`
- Pour relever un objet numéroté ou une fugace (ocre, terre rubéfiée, charbon, etc.) :
    - Sélectionner la couche `Objets` ou `Fugaces`
    - Mettre la couche en mode `Édition`
    - Cliquer sur le bouton `Ajouter une entité polygonale` et dessiner l'objet point par point
    - Pour terminer le dessin, appuyer longuement n'importe où, et le formulaire doit apparaître
    - Remplir le formulaire et valider
- Pour relever une esquille :
    - Sélectionner la couche `Esquilles`
    - Mettre la couche en mode `Édition`
    - Cliquer sur le bouton `Ajouter une entité ponctuelle` et dessiner l'esquille. Le formulaire doit apparaître
    - Remplir le formulaire et valider
- Pour supprimer un élément :
    - Sélectionner la bonne couche
    - Mettre la couche en mode `Édition`
    - Cliquer sur le bouton `Sélectionner une entité` et sélectionner l'élément à supprimer
    - Cliquer sur le bouton `Supprimer les entités sélectionnées`
- Pour visualiser ou modifier les attributs d'un élément :
    - Sélectionner la bonne couche
    - Mettre la couche en mode `Édition` pour modifier les attributs
    - Cliquer sur le bouton `Identifier des entités` et cliquer sur l'élément. Les attributs s'affichent à droite
    - On peut ouvrir le formulaire en cliquant sur le bouton `Afficher le formulaire de l'entité` dans le panneau `Résultats de l'identification`
- Pour afficher l'ensemble des éléments d'une couche avec leurs attributs :
    - Sélectionner la bonne couche
    - Cliquer sur le bouton `Ouvrir la table d'attributs`
- Penser à sauvegarder régulièrement les différentes couches en sortant du mode `Édition` ou en cliquant sur le bouton `Enregistrer les modifications de la couche`
- Si plus rien ne s'affiche, vérifier qu'on est au bon endroit (voir plus haut) et que la case `Rendu` en bas à droite de l'écran est cochée

# L'import des données

- Copier le fichier CSV de la station totale dans le dossier choisi dans la configuration (`Fichiers CSV de station totale`)
- Copier les dossiers des projets de terrain (dossiers contenant les fichiers `.qgs`) dans le dossier choisi dans la configuration (`Projets de terrain terminés`)
- Copier le dossier du projet `Esquilles` (dossier contenant le fichier `Esquilles.qgs`) dans le dossier choisi dans la configuration (`Projets de terrain terminés`)
- Ouvrir le projet QGIS `Pincevent`
- Menu `Extension`>`ArcheoSync`>`Importer des données`
- Les fichiers et dossiers de projets doivent être listés
- Sélectionner ceux à importer et cliquer sur `Importer`
- Un panneau d'import s'affiche avec les éventuelles erreurs détectées, et une ou plusieurs couches temporaires sont créées dans le projet `Pincevent` :
    - Une couche `New features` contenant les fugaces nouvellement importées depuis les tablettes
    - Une couche `New objects` contenant les objets nouvellement importés depuis les tablettes
    - Une couche `New small finds` contenant les esquilles nouvellement importées depuis les tablettes
    - Une couche `Imported_CSV_Points` contenant les points topo nouvellement importés
- Vérifier ces nouvelles données et modifier au besoin ces couches temporaires sans oublier d'en enregistrer les modifications
    Au fur et à mesure des corrections, la liste d'erreurs détectées peut être actualisée
- Le panneau d'import peut être rouvert en ouvrant le menu `Extension`>`ArcheoSync`>`Importer des données`
- Cliquer sur le bouton `Valider`. Les couches temporaires sont supprimées et les nouveaux éléments ajoutés aux couches `Objets`, `Fugaces`, `Points topo` et `Esquilles` et sélectionnées.
- Sauvegarder les modifications faites dans les couches `Objets`, `Fugaces`, `Points topo` et `Esquilles`