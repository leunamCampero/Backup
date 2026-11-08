SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Routes_services_chemins_agricoles_2x
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
						
-- Les voies particulières de type track et service
"highway" IN ('track','service','unclasified','residential','tertiary','secondary','primary')
AND
(   -- Elles ont un revetement circulable au VTC vélo de randonnée
    (
        (
            "surface" IN ('paved','asphalt','concrete','concrete:plates','concrete:lanes','paving_stones','sett','unhewn_cobblestone','cobblestone','metal','wood','unpaved','compacted','fine_gravel','gravel','pebblestone','ground','tartan','clay','metal_grid' )
            OR
            "surface" IS NULL
        )
        AND
        (
            "smoothness" NOT IN ('bad','very_bad','horrible','very_horrible','impassable')
            OR
            "smoothness" IS NULL
        )
        AND
        (
            "tracktype" NOT iN ('grade3','grade4','grade5')
            OR
            "tracktype" IS NULL
        )
    )
    AND
    (  -- on veux au moins que l'un des trois tags (surface, smoothness ou tracktype) soit renseigné pour les highway = track
        "highway" != 'track'
        OR
        "surface" IS NOT NULL
        OR
        "smoothness" IS NOT NULL
        OR
        "tracktype" IS NOT NULL
    )
)
AND
(	-- et dont l’accès n’est pas autorisé à certains types de véhicules motorisés
	(
		"psv" IS NULL
		OR
		"psv"='no'
	)
	AND
	(
		"motorcycle" IS NULL
		OR
		"motorcycle"='no'
	)
	AND
	(
		"bus" IS NULL
		OR
		"bus"='no'
	)
)
AND
(	-- et dont
	(	-- soit, l'accès est interdits aux voitures
		(
			"motor_vehicle" IN ('no','forestry','agricultural')
			OR
			"motorcar" IN ('no','forestry','agricultural')
		)
		AND
		(	-- mais n’est pas interdit aux vélos,
			(
				"bicycle" IS NULL
				OR
				"bicycle" NOT LIKE 'no'
			)
			AND
			(
				"access:bicycle" IS NULL
				OR
				"access:bicycle" NOT LIKE 'no'
			)
		)
	)
	OR
	(	-- soit, l'accès est interdits à tous
		"access" IN ('no','forestry','agricultural')
		AND
        ( -- mais est permis aux vélos
            "bicycle" IN ('yes','designated')
            OR
            "access:bicycle" IN ('yes','designated')
        )
        AND
        ( -- et n'est pas explicitement autorisée aux voitures
            "motor_vehicle" IS NULL
            OR
            "motor_vehicle" = 'no'
        )
	)
)
AND
(	-- Et qui ne sont pas à sens unique pour les vélos
	(
		"oneway" IS NULL
		OR
		"oneway" NOT IN ('yes','-1')
	)
	AND
	(
		"oneway:bicycle" IS NULL
		OR
		"oneway:bicycle" NOT IN ('yes','-1')
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;