import keg_mail.content as content


class TestEmailContent(object):
    def test_content_is_dedented(self):
        text = """
        stuff
        thing
        """
        cont = content.EmailContent(text, text)

        assert cont.text == "stuff\nthing"
        assert cont.html == "stuff\nthing"

    def test_content_isnt_dedented(self):
        text = """
        stuff
        thing
        """
        cont = content.EmailContent(text, text, clean_whitespace=False)
        assert cont.text == text
        assert cont.html == text

    def test_format_applys_kwargs(self):
        text = '{var}'

        cont = content.EmailContent(text, text)
        cont_replaced = cont.format(var='thing')
        assert cont != cont_replaced
        assert cont_replaced.text == 'thing'
        assert cont_replaced.html == 'thing'

    def test_join_combines_contents(self):
        cont1 = content.EmailContent('====', '====')
        cont2 = content.EmailContent('stuff', 'stuff')
        cont3 = content.EmailContent('thing', 'thing')
        cont4 = cont1.join([cont2, cont3])

        assert cont4.text == 'stuff====thing'
        assert cont4.html == 'stuff====thing'

    def test_equality(self):
        assert content.EmailContent('a', 'a') == content.EmailContent('a', 'a')
        assert content.EmailContent('b', 'a') != content.EmailContent('a', 'a')
        assert content.EmailContent('a', 'b') != content.EmailContent('a', 'a')
        assert content.EmailContent('b', 'b') != content.EmailContent('a', 'a')


class TestEmail(object):

    def setup_method(self):
        self.content = content.EmailContent('{a}', '{a}')
        self.content_b = content.EmailContent('{b}', '{b}')

    def test_equality(self):
        # Same
        assert (content.Email('a', self.content, 'a') ==
                content.Email('a', self.content, 'a'))

        # Different subject
        assert (content.Email('a', self.content, 'a') !=
                content.Email('b', self.content, 'a'))

        # Different content
        assert (content.Email('a', self.content, 'a') !=
                content.Email('a', self.content_b, 'a'))

        # Different type
        assert (content.Email('a', self.content, 'a') !=
                content.Email('a', self.content, 'b'))
