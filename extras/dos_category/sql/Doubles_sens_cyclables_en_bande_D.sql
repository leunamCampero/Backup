SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Doubles_sens_cyclables_en_bande_D
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
						-- Double-sens cyclables avec bandes (compter une fois)

-- Cas pour les opposite_lane

(	-- Une route à sens unique
	"oneway" IN ('yes','-1')
	AND
	(	-- qui a un DSC expicitement à droite
		"cycleway:right" LIKE 'opposite_lane'
	)		
)
OR
(	-- Une route à sens unique taguée avec oneway=-1
	"oneway" LIKE '-1'
	AND
	(
		"cycleway" = 'opposite_lane'
		OR
		(	-- qui a une bande cyclable à droite implicitement à contre sens du fait du -1
			"cycleway:right" LIKE 'lane'
			AND
			"oneway:bicycle" LIKE 'no'
			AND
			(	--et qui n'est pas à double sens 
				"cycleway:right:oneway" IS NULL
				OR
				"cycleway:right:oneway" NOT LIKE 'no'
			)	
		)
		OR
		(	-- qui a une bande cyclable à droite et à gauche et donc implicitement à contre sens
			"cycleway:both" LIKE 'lane'
			AND
			"oneway:bicycle" LIKE 'no'
		)
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;