SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Pistes_cyclables_2x
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
						(	-- A - Soit la route est à double sens avec des pistes cyclables ratachées de part et d'autre, soit il s'agit d'une piste cyclable indépendante à double sens :
	(	-- la route ou la piste cyclable est à double sens
		"oneway" IS NULL
		OR "oneway" NOT IN ('yes','-1')
	)
	AND	-- et elle est
	(	-- soit une piste cyclable indépendante
		"highway" LIKE 'cycleway'
		OR
		(	-- soit une piste cyclable rattachée à la route (track) de part et d'autre de la route
			"cycleway" IN ('track','opposite_track')
			OR
			"cycleway:both" IN ('track','opposite_track')
			OR
			(
				"cycleway:left" IN ('track','opposite_track')
				AND
				"cycleway:right" IN ('track','opposite_track')
			)
		)
	)
)


                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;