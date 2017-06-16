# -*- coding: utf-8 -*-
from flask import Flask
from flask_marshmallow import Marshmallow
from flask_marshmallow.mongoengine import HyperlinkRelated, url_for
from flask_mongoengine import MongoEngine, Document
from mongoengine import StringField, ReferenceField, ListField
from werkzeug.wrappers import BaseResponse
import pytest

from tests.conftest import Bunch
from tests.markers import marshmallow_2_req


@marshmallow_2_req
class TestMongoEngine:

    @pytest.yield_fixture()
    def extapp(self):
        app_ = Flask('extapp')
        app_.config['MONGODB_SETTINGS'] = {'db': 'testdb',
                            'host': 'mongodb://127.0.0.1',
                            'port': 27017,
                            'username': '',
                            'password': ''}

        MongoEngine(app_)
        Marshmallow(app_)

        @app_.route('/author/<objectid:id>')
        def author(id):
            return '...view for author {0}...'.format(id)

        @app_.route('/book/<objectid:id>')
        def book(id):
            return '...view for book {0}...'.format(id)

        ctx = app_.test_request_context()
        ctx.push()

        yield app_

        ctx.pop()

    @pytest.fixture()
    def extma(self, extapp):
        return extapp.extensions['flask-marshmallow']

    @pytest.yield_fixture()
    def models(self):
        class Author(Document):
            #__tablename__ = 'author'
            meta = {'collection': 'author'}

            #id = db.Column(db.Integer, primary_key=True)
            name = StringField(max_length=255)
            #name = db.Column(db.String(255))
            books = ListField(ReferenceField("Book"))

            @property
            def url(self):
                return url_for('author', id=self.id)

            @property
            def absolute_url(self):
                return url_for('author', id=self.id, _external=True)

        class Book(Document):
            #__tablename__ = 'book'
            meta = {'collection': 'book'}
            #id = db.Column(db.Integer, primary_key=True)

            title = StringField(max_length=255)
            author = ReferenceField("Author")
            @property
            def author_id(self):
                return self.author.id

            #title = db.Column(db.String(255))
            #author_id = db.Column(db.Integer, db.ForeignKey('author.id'))
            #author = db.relationship('AuthorModel', backref='books')

            @property
            def url(self):
                return url_for('book', id=self.id)

            @property
            def absolute_url(self):
                return url_for('book', id=self.id, _external=True)

        #db.create_all()
        yield Bunch(Author=Author, Book=Book)
        #db.drop_all()

        Book.drop_collection()
        Author.drop_collection()

    def test_can_declare_model_schemas(self, extma, models):
        class AuthorSchema(extma.ModelSchema):
            class Meta:
                model = models.Author

        class BookSchema(extma.ModelSchema):
            class Meta:
                model = models.Book

        author_schema = AuthorSchema()
        book_schema = BookSchema()

        author = models.Author(name='Chuck Paluhniuk')
        author.save()
        #db.session.add(author)
        #db.session.commit()

        author = models.Author(name='Chuck Paluhniuk')
        book = models.Book(title='Fight Club', author=author)
        author.save()
        book.save()
        author.books.append(book)
        author.save()
        #db.session.add(author)
        #db.session.add(book)
        #db.session.commit()

        author_result = author_schema.dump(author)
        assert 'id' in author_result.data
        assert 'name' in author_result.data
        assert author_result.data['name'] == 'Chuck Paluhniuk'
        assert author_result.data['books'][0] == str(book.id)

        book_result = book_schema.dump(book)
        assert 'id' in book_result.data
        assert book_result.data['author'] == str(author.id)

        resp = author_schema.jsonify(author)
        assert isinstance(resp, BaseResponse)

    def test_hyperlink_related_field(self, extma, models, extapp):
        class BookSchema(extma.ModelSchema):
            class Meta:
                model = models.Book
            author = extma.HyperlinkRelated('author')

        book_schema = BookSchema()

        author = models.Author(name='Chuck Paluhniuk')
        book = models.Book(title='Fight Club', author=author)
        author.save()
        book.save()
        #db.session.add(author)
        #db.session.add(book)
        #db.session.flush()

        print("book =", book.to_json())
        print("book =", book.to_mongo())
        print("book =", book._fields)
        print("book =", book._data)
        print("book =", book.__getstate__())


        book_result = book_schema.dump(book)
        assert book_result.data['author'] == author.url

        deserialized = book_schema.load(book_result.data)
        assert deserialized.data.author == author

    def test_hyperlink_related_field_errors(self, extma, models, extapp):
        class BookSchema(extma.ModelSchema):
            class Meta:
                model = models.Book
            author = HyperlinkRelated('author')

        book_schema = BookSchema()

        author = models.Author(name='Chuck Paluhniuk')
        book = models.Book(title='Fight Club', author=author)
        author.save()
        book.save()
        #db.session.add(author)
        #db.session.add(book)
        #db.session.flush()

        # Deserialization fails on bad endpoint
        book_result = book_schema.dump(book)
        book_result.data['author'] = book.url
        deserialized = book_schema.load(book_result.data)
        assert 'expected "author"' in deserialized.errors['author'][0]

        # Deserialization fails on bad URL key
        book_result = book_schema.dump(book)
        book_schema.fields['author'].url_key = 'pk'
        deserialized = book_schema.load(book_result.data)
        assert 'URL pattern "pk" not found' in deserialized.errors['author'][0]

    def test_hyperlink_related_field_external(self, extma, models, extapp):
        class BookSchema(extma.ModelSchema):
            class Meta:
                model = models.Book
            author = HyperlinkRelated('author', external=True)

        book_schema = BookSchema()

        author = models.Author(name='Chuck Paluhniuk')
        book = models.Book(title='Fight Club', author=author)
        author.save()
        book.save()
        #db.session.add(author)
        #db.session.add(book)
        #db.session.flush()

        book_result = book_schema.dump(book)
        assert book_result.data['author'] == author.absolute_url

        deserialized = book_schema.load(book_result.data)
        assert deserialized.data.author == author

    def test_hyperlink_related_field_list(self, extma, models, extapp):
        class AuthorSchema(extma.ModelSchema):
            class Meta:
                model = models.Author
            books = extma.List(HyperlinkRelated('book'))

        author_schema = AuthorSchema()

        author = models.Author(name='Chuck Paluhniuk')
        book = models.Book(title='Fight Club', author=author)
        author.save()
        book.save()
        #db.session.add(author)
        #db.session.add(book)
        #db.session.flush()

        author_result = author_schema.dump(author)
        assert author_result.data['books'][0] == book.url

        deserialized = author_schema.load(author_result.data)
        assert deserialized.data.books[0] == book
