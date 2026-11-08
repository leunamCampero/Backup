SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Bandes_cyclables_2xG
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
	(	-- une route à sens unique ou non, quand la bande de gauche est à double sens
		"cycleway:left" IN ('lane','opposite_lane')
		AND
		"cycleway:left:oneway" LIKE 'no'
	)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;