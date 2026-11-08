SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Pistes_cyclables_1xD
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
						(-- A - Soit la piste cyclable est séparée et à sens unique
	"oneway" IN ('yes')
	AND
	"highway" LIKE 'cycleway'
)

OR
(
	(	-- soit la piste cyclable est à droite de manière explicite sur une voie a double sens )
		"cycleway:right" IN ('track')
		AND
		(	-- et il n'y a pas de piste à gauche
			"cycleway:left" IS NULL
			OR
			"cycleway:left" NOT IN ('track','opposite_track')
		)
		AND
		(	-- et la piste de droite est bien à sens unique
			"cycleway:right:oneway" IS NULL
			OR
			"cycleway:right:oneway" NOT LIKE 'no'
		)
	)
	OR
	(	-- Soit qui ne sont que du coté de circulation des routes à sens unique
		(  -- route à sens unique (avec yes)
			"oneway"='yes'
		)
		AND
		(
			(--avec une bande cyclable
				"cycleway"='track'
					OR
				"cycleway:right"='track'
			)
			AND
			( --et pas a double sens 
				"cycleway:right:oneway" NOT LIKE 'no'
				OR
				"cycleway:right:oneway" IS NULL
			)
				
		)
	)
	OR
	(	-- route à sens unique (avec -1)
		"oneway"='-1'
		AND
		(
			"cycleway:right"='track' --avec une bande cyclable (obligatoirement left sinon il s'agit d'un double-sens cyclable)
			AND
			(	-- et pas à double sens
				"cycleway:right:oneway" IS NULL
				OR
				"cycleway:right:oneway" NOT LIKE 'no'
			)
			AND
			(	--et pas en en DSC
				"oneway:bicycle" NOT LIKE 'no'
				OR
				"oneway:bicycle" IS NULL
			)
		)
	)
)
	

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;