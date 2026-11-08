SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Bandes_cyclables_2x
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
	(	-- une route à double sens
		(
			"oneway" IS NULL
			OR
			"oneway" LIKE 'no'
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
		"cycleway" IN ('lane' , 'opposite_lane')
		OR
		(	-- soit une bande cyclable à droite et à gauche quelque soit le sens
			"cycleway:right" IN ('lane','opposite_lane')
			AND "cycleway:left" IN ('lane','opposite_lane')
		)
		OR	-- soit une bande cyclable à droite et à gauche quelque soit le sens
		"cycleway:both" IN ('lane','opposite_lane')
	)
	AND
	( --et qui ne comporte pas une seul voie sinon c'est un chaucidou
	    "lanes" IS NULL
	    OR
	    "lanes" NOT IN ('1')
	)
)


                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;