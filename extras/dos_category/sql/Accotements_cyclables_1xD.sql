SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Accotements_cyclables_1xD
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
						-- Les accotements cyclables comptées une fois sont :

(	-- Soit qui ne sont que d'un coté d'une route à double sens et sont à sens uniques
	(	-- voies à double sens
		"oneway" IS NULL
		OR
		"oneway" NOT IN ('yes','-1')
	)
	AND
	(	--bande cyclable d'un seul côté
		(	-- seulement à droite
			"cycleway:right"='shoulder'
			AND
			(	-- pas à gauche
				"cycleway:left" IS NULL
				OR
				"cycleway:left" NOT IN ('shoulder')
			)
		)
	)
)

OR
(	-- Soit qui ne sont que du coté de circulation des routes à sens unique 
	(	-- route à sens unique (avec yes)
		(
			"oneway"='yes'
			OR
			"junction" IN ('roundabout','circular')
		)
		AND
		(
			(--avec un accotement cyclable
				"cycleway"='shoulder'
					OR
				"cycleway:right"='shoulder'
			)
				
		)
	)
	OR
	(	-- route à sens unique (avec -1)
		"oneway"='-1'
		AND
		(
			"cycleway:left"='shoulder' --avec une bande cyclable (obligatoirement left sinon il s'agit d'un double-sens cyclable)

		)
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;