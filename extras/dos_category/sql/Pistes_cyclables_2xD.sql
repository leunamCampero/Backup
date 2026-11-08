SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Pistes_cyclables_2xD
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
						-- Une piste cyclable à double sens d'un seul côté de la route (:left/right), rattachée à une route (track) qui peut être à sens unique ou pas :
	(	-- ou la piste peut être à droite
		"cycleway:right" IN ('track','opposite_track')
		AND
		"cycleway:right:oneway" LIKE 'no'
	)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;