SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Bandes_cyclables_1xG
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
						-- Les bandes cyclables comptées une fois (et qui ne sont pas des doubles-sens cyclables) sont :

(	-- Soit qui ne sont que d'un coté d'une route à double sens et sont à sens uniques
	(	-- voies à double sens
		"oneway" IS NULL
		OR
		"oneway" NOT IN ('yes','-1')
	)
	AND
	(	--bande cyclable d'un seul côté
		(	-- seulement à gauche
			"cycleway:left"='lane'
			AND
			(	--pas à droite
				"cycleway:right" IS NULL
				OR
				"cycleway:right" NOT IN ('lane')
			)
			AND
			(	-- et pas à double sens
				"cycleway:left:oneway" IS NULL
				OR
				"cycleway:left:oneway" NOT LIKE 'no'
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
			(
				"cycleway:left" LIKE 'lane'
				AND
				(   --et pas en DSC
					"oneway:bicycle" NOT LIKE 'no'
					OR
					"oneway:bicycle" IS NULL
				)
				AND
				( --et pas a double sens 
					"cycleway:left:oneway" NOT LIKE 'no'
					OR
					"cycleway:left:oneway" IS NULL
				)
			)
		)
	)
	OR
	(	-- route à sens unique (avec -1)
		"oneway"='-1'
		AND
		(
			 --cas d'une bande a gauche du sens de circulation mais dans le sens de circulation
			(
				"cycleway:left" LIKE 'lane'
				OR
				"cycleway"='lane'
			)
			AND
			( --et pas a double sens 
				"cycleway:left:oneway" NOT LIKE 'no'
				OR
				"cycleway:left:oneway" IS NULL
			)
		)
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;