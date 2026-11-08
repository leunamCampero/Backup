SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Cheminements_cyclables_1xG
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
						-- Les cheminements cyclables comptées une fois sont :

(	-- Soit qui ne sont que d'un coté d'une route à double sens et sont à sens uniques
	(	-- voies à double sens
		"oneway" IS NULL
		OR
		"oneway" NOT IN ('yes','-1')
	)
	AND
	(	--cheminement cyclable d'un seul côté
		(	-- seulement à gauche
			"cycleway:left"='shared_lane'
			AND
			(	--pas à droite
				"cycleway:right" IS NULL
				OR
				"cycleway:right" NOT IN ('shared_lane')
			)
		)
	)
)

OR
(	-- Soit qui ne sont que du coté de circulation des routes à sens unique (obligatoirement left sinon il s'agit d'un double-sens cyclable)
	(	-- route à sens unique (avec yes)
		(
			"oneway"='yes'
			OR
			"junction" IN ('roundabout','circular')
		)
		AND
		( --cas d'une bande a gauche du sens de circulation mais dans le sens de circulation

            "cycleway:left" LIKE 'shared_lane'
			AND
			(
			    "oneway:bicycle" IS NULL
			    OR
			    "oneway:bicycle" != 'no'
			)
		)
	)
	OR
	(	-- route à sens unique (avec -1)
		"oneway"='-1'
		AND
		(
			 --cas d'une bande a gauche du way mais dans le sens de circulation
			(
				"cycleway:left" LIKE 'shared_lane'
				OR
				"cycleway"='shared_lane'
			)
		)
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;