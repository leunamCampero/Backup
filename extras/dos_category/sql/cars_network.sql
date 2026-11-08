SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as cars_network
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
						SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as cars_network
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
					(-- BEGIN CAR NETWORK SQL CONDITIONS
            "highway" IN (
                'motorway', 'motorway_link',
                'trunk', 'trunk_link',
                'primary', 'primary_link',
                'secondary', 'secondary_link',
                'tertiary', 'tertiary_link',
                'unclassified', 'residential',
                'living_street', 'service'
            )
            AND (
                "access" IS NULL 
                OR "access" NOT IN ('private', 'no')
            )
            AND (
                "motor_vehicle" IS NULL 
                OR "motor_vehicle" NOT IN ('private', 'no')
            )
            -- Optional: Include pedestrian roads that allow cars
            OR (
                "highway" = 'pedestrian'
                AND (
                    "motor_vehicle" IS NULL
                    OR "motor_vehicle" NOT IN ('no')
                )
            )
            -- END CAR NETWORK SQL CONDITIONS
        )
    ) row
) features;
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;