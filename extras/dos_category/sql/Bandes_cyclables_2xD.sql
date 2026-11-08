SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Bandes_cyclables_2xD
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
						--Soit
	(	-- une route à sens unique ou non, quand la bande de droite est à double sens
		"cycleway:right" IN ('lane','opposite_lane')
		AND
		"cycleway:right:oneway" LIKE 'no'
	)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;