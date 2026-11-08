
Requêtes Aménagements cyclables
==========================================

Ensemble de requêtes permettant d'extraire les aménagements cyclables des données OpenStreetMap.
Pour chaque type d'aménagement le suffixe indique si l'aménagement est unidirectionnel et le côté ou il se situe (1x pour unidirectionnel, 2x pour bidirectionnel, D pour côté droit et G pour côté Gauche (dans le sens de numérisation).

ex : 
* Bandes_cyclables-1xD : Bande cyclable unidirectionnel à droite
* Bandes_cyclables-2x : Bandes cyclables bidirectionnels une bande de chaque coté de la voie
* Bandes_cyclables-2xG :Bandes cyclables bidirectionnelles situées à gauche de la voie

Les requêtes aménagements sont exclusives, un aménagement ne sera donc répertorié que dans une seule des requêtes. 

Requêtes aménagements
---------------------------

* Bandes_cyclables
* Pistes_cyclables
* Accotements_cyclables : accotement revêtu ou bande multifonctionnelle
* Chaucidou : Chaussée à voie centrale banalisée
* Cheminements_cyclables : trajectoire cyclable matérialisée
* Doubles-sens_cyclables_sans_bande : Double sens cyclable non matérialisé au sol ou matérialisé uniquement par des pictogrammes
* Doubles-sens_cyclables_en_bande : Double sens cyclable matérialisé par une bande cyclable
* Doubles-sens_cyclables_piste : Double sens cyclable matérialisé par une piste cyclable (uniquement si modélisé sur la voie et non si la piste est modélisée sur une géométrie séparée)
* Trottoirs_cyclable : Trottoirs autorisés aux vélos où les flux cyclistes ne sont pas séparés des flux piétons
* Pistes_sur_Trottoirs : Trottoirs autorisés aux vélos où les flux cyclistes sont sont séparés des flux piétons
* Voies_bus : voies de bus ouvertes aux vélos
* Voies_vertes : Voies explicitement réservées aux piétons et aux vélos
* Routes_services_chemins_agricoles-1x.sql : Chemin agricole/forestier ou voie interdit aux véhicules à moteur  et ou les vélos sont autorisés
* Footway_path_designated : Cheminement piéton explicitement autorisé aux vélos
* Autres_chemins_piéton_autorisé_aux_vélos : Cheminement piéton autorisé aux vélos
* escalier : escaliers aménagés pour permettre le passage des vélos
* Footway_permissive : Voie ou les vélos sont tolérés

Requêtes voies apaisées
--------------------

* Pedestrian : Voies piétonnes
* Zones_30 : Zones 30
* limite_30 : Rue limitée à 30 Km/h
* Zones_rencontre : Zones de rencontre
* Vélorue : Vélorue



