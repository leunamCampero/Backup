SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Voies_bus_1xD
FROM
	(
		SELECT
			jsonb_build_object(
				'type',
				'Feature',
				'id',
				osm_id,
				'geometry',
				st_asgeojson(st_transform(way, 4326)) :: jsonb,
				'properties',
				to_jsonb(row) - 'gid' - 'geom'
			) AS feature
		FROM
			(
				SELECT
					*
				FROM
					planet_osm_line
				WHERE
					(
                        -- BEGIN GEOVELO SQL CONDITIONS
						(	-- A - Les cas où la voie est à sens unique
	"oneway" IN ('yes')
	AND
	(
		(
			(	-- A1 - Soit il s'agit de voies de bus indépendantes :
				"highway" IN ('service') -- des routes de service,
				AND
				(	-- accessibles aux bus,
					"psv" IN ('yes')
					OR
					"bus" IN ('yes')
				)
				AND
				(	-- interdites à tous les autres véhicules,
					"access" LIKE 'no' OR "motor_vehicle" LIKE 'no'
				)
				AND
				(	-- mais authorisées aux vélos.
					(
					"bicycle" IS NOT NULL
					AND
					"bicycle" NOT IN ('no')
					)
					OR
					"cycleway" IN ('share_busway')
				)
			)
		)
		OR
		(	-- A2 - Soit des voies de bus rattachées à une route en sens unique :
			"cycleway" IN ('share_busway') -- un accès pour les vélos à la voie bus
			AND
			(	-- et l'existance d'une voie bus
				"busway" IS NOT NULL
				AND
				"busway" NOT IN ('no','opposite_lane')
			)
		)
        OR
        ( --Soit il s'agit de voies de bus guidée ouverte aux vélo
            "highway" = 'bus_guideway'
            AND
            (	-- mais authorisées aux vélos.
                (
                "bicycle" IS NOT NULL
                AND
                "bicycle" NOT IN ('no')
                )
                OR
                "cycleway" IN ('share_busway')
                OR
                "cycleway:right" IN ('share_busway')
            )
        )
	)
)
OR
( 
	"oneway" = '-1'
	AND
	(
			"cycleway" IN ('share_busway','opposite_share_busway') -- un accès pour les vélos à la voie bus
			AND
			(	-- et l'existance d'une voie bus a contre sens 
				"busway" IN ('opposite_lane')
			)
	)
)	
	
-- B - Les cas où le coté est mentionné par le tag

OR
(	-- B1 - Le coté est signalé uniquement sur sur le tag busway :
	"cycleway" IN ('share_busway') -- un accès pour les vélos à la voie bus et,
	AND
	(
		( 	-- pour la voie de bus à droite :
			(	-- une voie de bus à droite
				"busway:right" IS NOT NULL
				AND
				"busway:right" NOT IN ('no')
			)
			AND
			(	-- et pas de voie de bus à gauche
				"busway:left" IS NULL
				OR
				"busway:left" = 'no'
			)
		)
	)
)


OR
(	-- B2 - Le coté est signalé sur le tag cycleway :
	(
		"cycleway:right" IN ('share_busway','opposite_share_busway')
		AND
		(
			"cycleway:left" IS NULL
			OR
			"cycleway:left" NOT IN ('share_busway','opposite_share_busway')
		)
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;