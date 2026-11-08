SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as escalier_2x
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
						
-- Sont comptabilisés uniquement les escaliers ayant un aménagement pour les vélos

"highway" = 'steps' -- un escalier

AND

(
    "ramp:bicycle" = 'yes' --avec une goulotte pour les vélos sans précision de coté
    OR
    "ramp:bicycle:both" = 'yes'
    OR
    (  --avec une goulotte pour les vélos de chaque coté
        "ramp:bicycle:right" = 'yes'
        AND
        "ramp:bicycle:left" = 'yes'
    )
)
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;