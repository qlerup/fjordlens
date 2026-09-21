import unittest
import app as fl
import test_gallery_browse as fixtures


class PersonSearchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GalleryBrowseTests()
        self.fixture.setUp()
        self.client = self.fixture._authenticated_client()
        with fl.closing(fl.get_conn()) as conn:
            for name, hidden in [('Christian Hansen', 0), ('Christina', 0), ('Clara', 0), ('Secret', 1), ('Ukendt-3', 0), ('Private', 0)]:
                conn.execute('INSERT INTO people(name,hidden,created_at) VALUES(?,?,?)', (name, hidden, fl.now_iso()))
            for name in ['IMG_1.jpg', 'IMG_2.jpg', 'other.jpg']:
                conn.execute('INSERT INTO photos(rel_path,filename) VALUES(?,?)', ('uploads/originals/Album/'+name, name))
            conn.execute("INSERT INTO photos(rel_path,filename) VALUES('uploads/originals/Private/private.jpg','private.jpg')")
            for photo, people in [(1, [1, 2]), (2, [1]), (3, [3, 4, 5]), (4, [6])]:
                for person in people:
                    conn.execute('INSERT INTO faces(photo_id,person_id,created_at) VALUES(?,?,?)', (photo, person, fl.now_iso()))
            fl._set_user_allowed_folders(conn, 2, [{'folder_path': 'Album', 'permission': 'view'}])
            conn.commit()

    def tearDown(self):
        self.fixture.tearDown()

    def test_suggestions_are_prefix_filtered_and_exclude_hidden_unknown(self):
        for prefix, names in [('', ['Christian Hansen', 'Christina', 'Clara', 'Private']),
                              ('c', ['Christian Hansen', 'Christina', 'Clara']),
                              ('Ch', ['Christian Hansen', 'Christina']), ('rist', [])]:
            data = self.client.get('/api/people/suggest', query_string={'q': prefix}).get_json()
            self.assertEqual([item['name'] for item in data['items']], names)

    def test_suggestions_respect_folder_access(self):
        data = self.fixture._authenticated_client(2).get('/api/people/suggest').get_json()
        self.assertEqual([p['name'] for p in data['items']], ['Christian Hansen', 'Christina', 'Clara'])

    def test_people_and_filename_filters_are_combined_before_pagination(self):
        first = self.fixture.page(self.client, 'mapper', folder='Album', person='1', limit=1, sort='name_asc')
        last = self.fixture.page(self.client, 'mapper', folder='Album', person='1', limit=1,
                                 sort='name_asc', offset=first['next_offset'])
        self.assertEqual([p['filename'] for p in first['items']+last['items']], ['IMG_1.jpg', 'IMG_2.jpg'])
        self.assertTrue(first['has_more'])
        self.assertFalse(last['has_more'])
        both = self.fixture.page(self.client, person=['1', '2'], q='IMG')
        self.assertEqual([p['filename'] for p in both['items']], ['IMG_1.jpg'])
        self.assertEqual(self.fixture.page(self.client, person='1', q='other')['items'], [])

    def test_hidden_and_inaccessible_person_filters_return_no_photos(self):
        self.assertEqual(self.fixture.page(self.client, person='4')['items'], [])
        viewer = self.fixture._authenticated_client(2)
        self.assertEqual(self.fixture.page(viewer, person='6')['items'], [])
        self.assertEqual(self.client.get('/api/photos?person=bad').status_code, 400)
