SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Double_sens_cyclables_sans_bande
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
						-- Soit tagué avec le schema opposite

(	-- une route à sens unique
	"oneway" IN ('yes','-1')
	AND
	(	-- qui a un contre-sens à gauche
		"cycleway" = 'opposite'
		OR	-- ou qui a un contre-sens à gauche explicite
		"cycleway:left" = 'opposite'
		OR	-- qui a un contre-sens à droite explicite
		"cycleway:right" = 'opposite'
	)
)

-- Soit tagué avec oneway:bicycle=no en distinguant oneway=yes et oneway=-1

OR
(	-- Une route à sense unique taguée avec oneway=yes
	"oneway" = 'yes'
	AND -- qui n'est pas à sens unique pour les vélo
	"oneway:bicycle" = 'no'
	AND 
	(	-- qui n'a pas d'autres informations concernant des aménagements cyclables
		(	-- qui n'a pas de bande cyclable ou de piste cyclable à contre-sens
			"cycleway" IS NULL
			OR 
			"cycleway" IN ('no','shared_lane')
		)
		AND
		(	-- qui n'a pas de bande cyclable à contre sens
			"cycleway:left" IS NULL
			OR
			"cycleway:left" IN ('no','shared_lane')
		)
		AND
		(	-- qui n'a pas de banse cyclable de chaque côté explicitement
			"cycleway:both" IS NULL
			OR
			"cycleway:both" IN ('no','shared_lane')
		)
		AND
		(  -- qui n'a pas de piste a droite à double sens
		    "cycleway:right:oneway" IS NULL
		    OR
		    "cycleway:right:oneway" != 'no'
		)
	)
)
OR
(
	"oneway" IN ('-1')
	AND
	"oneway:bicycle" = 'no'
	AND 
	(
		(
			"cycleway" IS NULL
			OR 
			"cycleway" IN ('no','shared_lane')
		)
		AND
		(
			"cycleway:right" IS NULL
			OR
			"cycleway:right" IN ('no','shared_lane')
		)
		AND
		(
			"cycleway:both" IS NULL
			OR
			"cycleway:both" IN ('no','shared_lane')
		)
		AND
		(  -- qui n'a pas de piste a droite à double sens
		    "cycleway:left:oneway" IS NULL
		    OR
		    "cycleway:left:oneway" != 'no'
		)
	)
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;