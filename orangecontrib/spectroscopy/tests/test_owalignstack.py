import unittest
from unittest.mock import Mock, patch

import numpy as np
from scipy.ndimage import sobel

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.spectroscopy.data import _spectra_from_image, build_spec_table
from orangecontrib.spectroscopy.widgets.owstackalign import \
    alignstack, RegisterTranslation, shift_fill, OWStackAlign


def test_image():
    return np.hstack((np.zeros((5, 1)),
                      np.diag([1, 5., 3., 1, 1]),
                      np.ones((5, 1))))


def _up(im, fill=0):
    return np.vstack((im[1:],
                      np.ones_like(im[0]) * fill))


def _down(im, fill=0):
    return np.vstack((np.ones_like(im[0]) * fill,
                      im[:-1]))


def _right(im, fill=0):
    return np.hstack((np.ones_like(im[:, :1]) * fill,
                      im[:, :-1]))


def _left(im, fill=0):
    return np.hstack((im[:, 1:],
                      np.ones_like(im[:, :1]) * fill))


class TestUtils(unittest.TestCase):

    def test_image_shift(self):
        im = test_image()
        calculate_shift = RegisterTranslation()
        s = calculate_shift(im, _up(im))
        np.testing.assert_equal(s, (1, 0))
        s = calculate_shift(im, _down(im))
        np.testing.assert_equal(s, (-1, 0))
        s = calculate_shift(im, _left(im))
        np.testing.assert_equal(s, (0, 1))
        s = calculate_shift(im, _right(im))
        np.testing.assert_equal(s, (0, -1))
        s = calculate_shift(im, _left(_left(im)))
        np.testing.assert_equal(s, (0, 2))

    def test_alignstack(self):
        im = test_image()
        _, aligned = alignstack([im, _up(im), _down(im), _right(im)],
                                shiftfn=RegisterTranslation())
        self.assertEqual(aligned.shape, (4, 5, 7))

    def test_alignstack_calls_filterfn(self):
        filterfn = Mock()
        filterfn.side_effect = lambda x: x
        im = test_image()
        up = _up(im)
        down = _down(im)
        alignstack([im, up, down],
                   shiftfn=RegisterTranslation(),
                   filterfn=filterfn)
        for i, t in enumerate([im, up, down]):
            self.assertIs(filterfn.call_args_list[i][0][0], t)

    def test_shift_fill(self):
        im = test_image()

        # shift down
        a = shift_fill(im, (1, 0))
        np.testing.assert_almost_equal(a, _down(im, np.nan))
        a = shift_fill(im, (0.55, 0))
        np.testing.assert_equal(np.isnan(a), np.isnan(_down(im, np.nan)))
        a = shift_fill(im, (0.45, 0))
        np.testing.assert_equal(np.isnan(a), False)

        # shift up
        a = shift_fill(im, (-1, 0))
        np.testing.assert_almost_equal(a, _up(im, np.nan))
        a = shift_fill(im, (-0.55, 0))
        np.testing.assert_equal(np.isnan(a), np.isnan(_up(im, np.nan)))
        a = shift_fill(im, (-0.45, 0))
        np.testing.assert_equal(np.isnan(a), False)

        # shift right
        a = shift_fill(im, (0, 1))
        np.testing.assert_almost_equal(a, _right(im, np.nan))
        a = shift_fill(im, (0, 0.55))
        np.testing.assert_equal(np.isnan(a), np.isnan(_right(im, np.nan)))
        a = shift_fill(im, (0, 0.45))
        np.testing.assert_equal(np.isnan(a), False)

        # shift left
        a = shift_fill(im, (0, -1))
        np.testing.assert_almost_equal(a, _left(im, np.nan))
        a = shift_fill(im, (0, -0.55))
        np.testing.assert_equal(np.isnan(a), np.isnan(_left(im, np.nan)))
        a = shift_fill(im, (0, -0.45))
        np.testing.assert_equal(np.isnan(a), False)


def diamond():
    return np.array([
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 6, 1, 1, 0, 0, 0],
        [0, 0, 1, 1, 5, 1, 7, 1, 1, 0, 0],
        [0, 0, 0, 1, 1, 8, 1, 1, 0, 0, 0],
        [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=float)


def fake_stxm_from_image(image):
    spectral = np.zeros(image.shape + (5,))
    spectral[:, :, 0] = diamond()
    spectral[:, :, 1] = _up(diamond())
    spectral[:, :, 2] = _down(diamond())
    spectral[:, :, 3] = _right(diamond())
    spectral[:, :, 4] = _down(_right(_down(diamond())))
    return spectral


def orange_table_from_3d(image3d):
    info = _spectra_from_image(image3d,
                               range(5),
                               range(image3d[:, :, 0].shape[1]),
                               range(image3d[:, :, 0].shape[0]))
    data = build_spec_table(*info)
    return data


stxm_diamond = orange_table_from_3d(fake_stxm_from_image(diamond()))


def orange_table_to_3d(data):
    nz = len(data.domain.attributes)
    minx = int(min(data.metas[:, 0]))
    miny = int(min(data.metas[:, 1]))
    maxx = int(max(data.metas[:, 0]))
    maxy = int(max(data.metas[:, 1]))
    image3d = np.ones((maxy-miny+1, maxx-minx+1, nz)) * np.nan
    for d in data:
        x, y = int(d.metas[0]), int(d.metas[1])
        image3d[y - miny, x - minx, :] = d.x
    return image3d


class TestOWStackAlign(WidgetTest):

    def setUp(self):
        self.widget = self.create_widget(OWStackAlign)

    def test_add_remove_data(self):
        self.send_signal(OWStackAlign.Inputs.data, stxm_diamond)
        out = self.get_output(OWStackAlign.Outputs.newstack)
        self.assertIsInstance(out, Table)
        self.send_signal(OWStackAlign.Inputs.data, None)
        out = self.get_output(OWStackAlign.Outputs.newstack)
        self.assertIs(out, None)

    def test_output_aligned(self):
        self.send_signal(OWStackAlign.Inputs.data, stxm_diamond)
        out = self.get_output(OWStackAlign.Outputs.newstack)
        image3d = orange_table_to_3d(out)
        for z in range(1, image3d.shape[2]):
            np.testing.assert_almost_equal(image3d[:, :, 0], image3d[:, :, z])

    def test_output_cropped(self):
        self.send_signal(OWStackAlign.Inputs.data, stxm_diamond)
        out = self.get_output(OWStackAlign.Outputs.newstack)
        image3d = orange_table_to_3d(out)
        # for a cropped image all have to be defined
        self.assertFalse(np.any(np.isnan(image3d)))
        # for diamond test data, extreme movement
        # in X was just one right,
        # in Y was one up and 2 down
        # try to crop manually to see if the obtained image is the same
        np.testing.assert_equal(image3d[:, :, 0], diamond()[1:-2, :-1])

    def test_sobel_called(self):
        with patch("orangecontrib.spectroscopy.widgets.owstackalign.sobel",
                   Mock(side_effect=sobel)) as mock:
            self.send_signal(OWStackAlign.Inputs.data, stxm_diamond)
            _ = self.get_output(OWStackAlign.Outputs.newstack)
            self.assertFalse(mock.called)
            self.widget.controls.sobel_filter.toggle()
            _ = self.get_output(OWStackAlign.Outputs.newstack)
            self.assertTrue(mock.called)

    def test_report(self):
        self.send_signal(OWStackAlign.Inputs.data, stxm_diamond)
        self.widget.send_report()
