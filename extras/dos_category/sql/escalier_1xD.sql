SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as escalier_1xD
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
--avec une goulotte pour les vélos sur le coté droit
"ramp:bicycle:right" = 'yes'
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;