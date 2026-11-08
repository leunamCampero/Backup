SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Doubles_sens_cyclables_piste_G
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
						-- Double-sens cyclables piste (compter une fois)

-- Cas pour les opposite_track

(	-- Une route à sens unique
	"oneway" IN ('yes','-1')
	AND
	(	-- qui a une bande cyclable expicitement à contre sens
		"cycleway:left" LIKE 'opposite_track'
	)		
)
		

OR
(	-- Une route à sens unique taguée avec oneway=yes
	"oneway" LIKE 'yes'
	AND
	(
		"cycleway" = 'opposite_track'
		OR
		(		-- qui a une bande cyclable à gauche implicitement à contre sens
			"cycleway:left" LIKE 'track'
			AND
			"oneway:bicycle" LIKE 'no'
			AND
			(	--et pas en double sens
				"cycleway:left:oneway" IS NULL
				OR
				"cycleway:left:oneway" NOT LIKE 'no'
			)
		)
		OR
		(	-- qui a une bande cyclable à droite et à gauche et donc implicitement à contre sens
			"cycleway:both" LIKE 'track'
			AND
			"oneway:bicycle" LIKE 'no'
		)
		
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;