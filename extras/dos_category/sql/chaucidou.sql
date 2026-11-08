SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as chaucidou
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
						(	-- Soit
	(	-- une route explicitement à double sens
		(
			"oneway" LIKE 'no' OR oneway IS NULL
		)
		AND
		(
			"junction" IS NULL
			OR
			"junction" NOT IN ('roundabout','circular')
		)
	)
	AND --et qui a
	(	-- soit une bande cyclable classique
		"cycleway" = 'lane'
		OR
		(	-- soit une bande cyclable à droite et à gauche quelque soit le sens
			"cycleway:right" = 'lane'
			AND "cycleway:left" = 'lane'
		)
		OR	-- soit une bande cyclable à droite et à gauche quelque soit le sens
		"cycleway:both" = 'lane'
	)
	AND -- et qui ne comporte q'une seule voie
	(
	    "lanes" = '1'
	)
)
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;