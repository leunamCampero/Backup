SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Voies_vertes_2x
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
						(
	(
		"oneway" IS NULL
		OR
		"oneway" LIKE 'no'
	)
	AND
	(
		"oneway:bicycle" IS NULL
		OR
		"oneway:bicycle" LIKE 'no'
	)
)
AND
(
	(
		"highway" = 'path'
		AND
		"bicycle" = 'designated'
		AND
		"foot" = 'designated'
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;